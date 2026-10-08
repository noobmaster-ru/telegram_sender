import contextlib
import io
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon.errors import FloodWaitError
from telethon.extensions import markdown
from telethon.tl.types import MessageEntityTextUrl

import config
import main


logging.disable(logging.CRITICAL)


def mock_client():
    return SimpleNamespace(
        start=AsyncMock(),
        disconnect=AsyncMock(),
        send_message=AsyncMock(return_value=SimpleNamespace(id=42)),
        send_file=AsyncMock(return_value=SimpleNamespace(id=42)),
        get_messages=AsyncMock(return_value=SimpleNamespace(id=42)),
    )


class LocalPreviewTests(unittest.TestCase):
    def test_dry_run_needs_no_credentials_or_telegram_client(self):
        output = io.StringIO()
        with (
            patch.object(main, "TelegramClient", side_effect=AssertionError("Telegram подключён")),
            patch.object(main, "load_dotenv", side_effect=AssertionError("Секреты прочитаны")),
            contextlib.redirect_stdout(output),
        ):
            main.cli(["--dry-run"])
        self.assertIn("Каталог **бесплатно**. [Попробуйте👇]", output.getvalue())
        self.assertIn(str(config.MINIAPP_IMAGE_PATH), output.getvalue())
        self.assertIn("https://t.me/korzina_market_bot", output.getvalue())
        self.assertNotIn("cashback", sys.modules)
        self.assertNotIn("photos", sys.modules)

    def test_telegram_markdown_keeps_link_and_conditions(self):
        text, entities = markdown.parse(main.build_post().caption)
        links = [entity.url for entity in entities if isinstance(entity, MessageEntityTextUrl)]
        self.assertEqual(links, ["https://t.me/korzina_market_bot"])
        self.assertEqual(text, "Пока ждёте раздачу 👀\n\n"
            "«Корзина.Маркет» — маркетплейс с товарами с оптовых рынков: Садовода, ТЯК и Южных Ворот.\n\n"
            "Каталог бесплатно. Попробуйте👇")
        self.assertLessEqual(len(text.encode("utf-16-le")) // 2, 1024)

    def test_empty_or_oversized_post_fails_before_sending(self):
        for caption in ("   ", "🛒" * 513):
            with self.subTest(caption_length=len(caption)):
                with patch.object(config, "build_miniapp_caption", return_value=caption):
                    with self.assertRaises(ValueError):
                        main.build_post()

    def test_missing_or_empty_photo_fails_before_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / "cover.png"
            for exists in (False, True):
                if exists:
                    photo.touch()
                with (
                    self.subTest(exists=exists),
                    patch.object(config, "MINIAPP_IMAGE_PATH", photo),
                    patch.object(main, "TelegramClient") as client,
                ):
                    with self.assertRaises(ValueError):
                        main.cli(["--dry-run"])
                    client.assert_not_called()


class SendingTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_only_sends_to_report_chat(self):
        client = mock_client()
        with patch.object(main, "broadcast", new_callable=AsyncMock) as broadcast:
            await main.main(client, preview=True)
        broadcast.assert_not_awaited()
        client.send_file.assert_awaited_once_with(
            config.REPORT_CHAT, str(main.build_post().photo),
            caption=main.build_post().caption,
            parse_mode="markdown", force_document=False,
        )
        client.send_message.assert_not_awaited()
        client.disconnect.assert_awaited_once()

    async def test_failed_preview_disconnects(self):
        client = mock_client()
        client.send_file.side_effect = RuntimeError("Ошибка Telegram")
        with self.assertRaises(RuntimeError):
            await main.main(client, preview=True)
        client.disconnect.assert_awaited_once()

    async def test_failed_start_disconnects(self):
        client = mock_client()
        client.start.side_effect = RuntimeError("Ошибка подключения")
        with self.assertRaises(RuntimeError):
            await main.main(client, preview=True)
        client.send_message.assert_not_awaited()
        client.send_file.assert_not_awaited()
        client.disconnect.assert_awaited_once()

    async def test_flood_wait_retries_same_photo_and_caption_after_required_delay(self):
        client = mock_client()
        message = SimpleNamespace(id=17)
        client.send_file.side_effect = [FloodWaitError(request=None, capture=20), message]
        with patch.object(main.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            result = await main._send_with_flood_retry(client, "@allowed", main.build_post())
        self.assertIs(result, message)
        sleep.assert_awaited_once_with(25)
        self.assertEqual(client.send_file.await_args_list[0], client.send_file.await_args_list[1])
        client.send_message.assert_not_awaited()

    async def test_flood_wait_stops_after_retry_limit(self):
        client = mock_client()
        client.send_file.side_effect = FloodWaitError(request=None, capture=20)
        with patch.object(main.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            with self.assertRaises(FloodWaitError):
                await main._send_with_flood_retry(client, "@allowed", main.build_post())
        self.assertEqual(client.send_file.await_count, 3)
        self.assertEqual(sleep.await_count, 2)

    async def test_full_broadcast_excludes_channels_and_reports_same_photo_post(self):
        client = mock_client()
        excluded = next(iter(config.EXCLUDED_TARGETS))
        with tempfile.TemporaryDirectory() as directory:
            targets = Path(directory) / "targets.txt"
            targets.write_text(f"@allowed\n{excluded}\n\n", encoding="utf-8")
            with (
                patch.object(config, "TARGETS_FILE", str(targets)),
                patch.object(main.asyncio, "sleep", new_callable=AsyncMock),
                patch.object(main.random, "shuffle"),
            ):
                await main.main(client)
        calls = client.send_file.await_args_list
        destinations = [call.args[0] for call in calls]
        self.assertEqual(destinations.count("@allowed"), 1)
        self.assertNotIn(excluded, destinations)
        self.assertEqual(len(calls), 2)  # канал и точная копия в отчёте
        for call in calls:
            self.assertEqual(call.args[1], str(main.build_post().photo))
            self.assertEqual(call.kwargs["caption"], main.build_post().caption)
        self.assertIn("Каналов в рассылке: **1**", client.send_message.await_args.args[1])
        client.get_messages.assert_awaited_once_with("@allowed", ids=42)
        client.disconnect.assert_awaited_once()

    async def test_daily_uses_separate_folder_and_target_list(self):
        client = mock_client()
        with patch.object(main, "broadcast", new_callable=AsyncMock) as broadcast:
            await main.main(client, daily=True)
        self.assertEqual(broadcast.await_args.args[2:4], (config.FOLDER_NAME_DAILY, config.TARGETS_FILE_DAILY))
        client.disconnect.assert_awaited_once()

    async def test_missing_folder_reports_warning_without_broadcast(self):
        client = mock_client()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(config, "TARGETS_FILE", str(Path(directory) / "missing.txt")),
                patch.object(main.export_folder_chats, "export_chats", new_callable=AsyncMock) as export,
            ):
                await main.main(client)
        export.assert_awaited_once()
        client.send_message.assert_awaited_once()
        self.assertIn("Рассылка не запущена", client.send_message.await_args.args[1])
        client.send_file.assert_not_awaited()
        client.disconnect.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

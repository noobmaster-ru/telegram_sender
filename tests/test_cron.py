import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import config


DEPLOY = Path(__file__).resolve().parents[1] / "deploy"


class CronTests(unittest.TestCase):
    def test_utc_hours_match_five_moscow_broadcasts(self):
        cron = (DEPLOY / "telegram-sender.cron.utc").read_text()
        job = next(line for line in cron.splitlines() if line.endswith(" broadcast"))
        minute, hours, day, month, weekday, user, command, mode = job.split()
        moscow_hours = tuple((int(hour) + 3) % 24 for hour in hours.split(","))
        self.assertEqual(moscow_hours, config.BROADCAST_HOURS)
        self.assertEqual((minute, day, month, weekday), ("0", "*", "*", "*"))
        self.assertEqual(user, "root")  # Docker запускает процесс под непривилегированным UID.
        self.assertTrue(cron.endswith("\n"))

    @unittest.skipUnless(Path("/usr/bin/flock").exists(), "flock нужен на Linux-сервере")
    def test_broadcast_and_export_cannot_use_session_together(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            app, state, logs = (base / name for name in ("app", "state", "logs"))
            for path in (app / ".venv/bin", state, logs):
                path.mkdir(parents=True)
            interpreter = app / ".venv/bin/python"
            interpreter.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$1" >> "$TELEGRAM_SENDER_STATE_DIR/launched"\n'
                'touch "$TELEGRAM_SENDER_STATE_DIR/ready"\n'
                'while [ ! -e "$TELEGRAM_SENDER_STATE_DIR/release" ]; do sleep 0.05; done\n'
            )
            interpreter.chmod(0o700)
            env = dict(os.environ, TELEGRAM_SENDER_RUNNER="native", TELEGRAM_SENDER_APP_DIR=str(app),
                       TELEGRAM_SENDER_STATE_DIR=str(state), TELEGRAM_SENDER_LOG_DIR=str(logs))
            first = subprocess.Popen(["sh", str(DEPLOY / "run-scheduled.sh"), "broadcast"], env=env)
            try:
                deadline = time.monotonic() + 5
                while not (state / "ready").exists():
                    if time.monotonic() > deadline:
                        self.fail("Первая задача не запустилась")
                    time.sleep(0.02)
                second = subprocess.run(["sh", str(DEPLOY / "run-scheduled.sh"), "targets"],
                                        env=env, timeout=5)
                self.assertEqual(second.returncode, 0)
                self.assertEqual(len((state / "launched").read_text().splitlines()), 1)
                self.assertIn("пропуск", (logs / "scheduler.log").read_text())
                (state / "release").touch()
                self.assertEqual(first.wait(timeout=5), 0)
            finally:
                if first.poll() is None:
                    first.kill()
                    first.wait()


if __name__ == "__main__":
    unittest.main()

#!/bin/sh
# Запускать в консоли сервера под root. После успешного входа включает порученный cron.
set -eu
umask 077
export TZ=Europe/Moscow
app_dir=/opt/telegram-sender
state_dir=/var/lib/telegram-sender
log_dir=/var/log/telegram-sender
image=telegram-sender-runtime:20261005

if [ "$(id -u)" != 0 ]; then
  printf '%s\n' 'Запустите команду под root.' >&2
  exit 1
fi
if [ "$(timedatectl show -p Timezone --value)" != Etc/UTC ]; then
  printf '%s\n' 'Часовой пояс сервера изменился; UTC-шаблон cron применять нельзя.' >&2
  exit 1
fi
cd "$state_dir"
exec 9>"$state_dir/run.lock"
if ! /usr/bin/flock -n 9; then
  printf '%s\n' 'Сессия занята другой задачей; дождитесь её завершения.' >&2
  exit 1
fi

run_python() {
  /usr/bin/docker run --rm --pull=never \
    --user "$(id -u telegram-sender):$(id -g telegram-sender)" \
    --cap-drop ALL --security-opt no-new-privileges \
    --memory 256m --cpus 0.5 --pids-limit 128 \
    --env TZ=Europe/Moscow --env PYTHONUNBUFFERED=1 --env PYTHONDONTWRITEBYTECODE=1 \
    --volume "$app_dir:/code:ro" --volume "$state_dir:/state" \
    --workdir /state "$@"
}

run_python --interactive --tty --entrypoint /app/.venv/bin/python "$image" /code/deploy/login.py
run_python --entrypoint /app/.venv/bin/python "$image" /code/deploy/check-session.py
if ! run_python --entrypoint /app/.venv/bin/python "$image" /code/deploy/prepare-targets.py >> "$log_dir/prepare-targets.log" 2>&1; then
  printf '%s\n' 'Не удалось подготовить каналы. Cron не включён; подробности в prepare-targets.log.' >&2
  exit 1
fi

# Не допускаем одновременный возврат прежнего Ofelia.
if /usr/bin/docker inspect telegram_sender-scheduler-1 >/dev/null 2>&1; then
  /usr/bin/docker update --restart=no telegram_sender-scheduler-1 >/dev/null
  /usr/bin/docker stop telegram_sender-scheduler-1 >/dev/null
fi
install -o root -g root -m 644 "$app_dir/deploy/telegram-sender.logrotate" /etc/logrotate.d/telegram-sender
install -o root -g root -m 644 "$app_dir/deploy/telegram-sender.cron.utc" /etc/cron.d/telegram-sender
printf '%s\n' 'Cron включён: 07:00, 12:00, 16:00, 19:00 и 21:00 МСК. Сейчас рассылка не запускалась.'

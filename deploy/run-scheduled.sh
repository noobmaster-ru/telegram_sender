#!/bin/sh
# Общая блокировка для всех задач, использующих sender_session.session.
set -eu
umask 077
export TZ=Europe/Moscow

app_dir=${TELEGRAM_SENDER_APP_DIR:-/opt/telegram-sender}
state_dir=${TELEGRAM_SENDER_STATE_DIR:-/var/lib/telegram-sender}
log_dir=${TELEGRAM_SENDER_LOG_DIR:-/var/log/telegram-sender}
runner=${TELEGRAM_SENDER_RUNNER:-docker}
image=${TELEGRAM_SENDER_IMAGE:-telegram-sender-runtime:20261005}

case "${1:-}" in
  broadcast) script=main.py ;;
  targets) script=export_folder_chats.py ;;
  check-session) script=deploy/check-session.py ;;
  *) printf '%s\n' 'Использование: run-scheduled.sh broadcast|targets|check-session' >&2; exit 2 ;;
esac

case "$runner" in
  docker|native) ;;
  *) printf '%s\n' 'Неизвестный способ запуска' >&2; exit 2 ;;
esac

run_script() {
  if [ "$runner" = native ]; then
    "$app_dir/.venv/bin/python" "$app_dir/$script"
  else
    /usr/bin/docker run --rm --pull=never \
      --user "$(id -u telegram-sender):$(id -g telegram-sender)" \
      --cap-drop ALL --security-opt no-new-privileges \
      --memory 256m --cpus 0.5 --pids-limit 128 \
      --env TZ=Europe/Moscow --env PYTHONUNBUFFERED=1 --env PYTHONDONTWRITEBYTECODE=1 \
      --volume "$app_dir:/code:ro" --volume "$state_dir:/state" \
      --workdir /state --entrypoint /app/.venv/bin/python \
      "$image" "/code/$script"
  fi
}

cd "$state_dir"
exec 9>"$state_dir/run.lock"
if ! /usr/bin/flock -n 9; then
  printf '%s %s: пропуск — другой клиент уже использует сессию\n' "$(date -Is)" "$1" >> "$log_dir/scheduler.log"
  exit 0
fi

printf '%s %s: запуск\n' "$(date -Is)" "$1" >> "$log_dir/scheduler.log"
if run_script >> "$log_dir/$1.log" 2>&1; then
  printf '%s %s: завершено успешно\n' "$(date -Is)" "$1" >> "$log_dir/scheduler.log"
else
  result=$?
  printf '%s %s: ошибка, код %s\n' "$(date -Is)" "$1" "$result" >> "$log_dir/scheduler.log"
  exit "$result"
fi

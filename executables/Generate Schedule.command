#!/bin/zsh
set -u
cd "$(dirname "$0")/.."

PYTHON="./.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

echo "Validating UNIVERSAL_SCHEDULER.md..."
echo
"$PYTHON" scripts/compile_universal_scheduler.py --check || {
  echo
  read -r "?Press Enter to close..."
  exit 1
}

echo
echo "Generating schedule..."
echo
"$PYTHON" scripts/generate_schedule.py
exit_code=$?
echo
if [ $exit_code -eq 0 ]; then
  echo "Schedule generation finished."
else
  echo "Schedule generation failed. Review the messages above."
fi

echo
read -r "?Press Enter to close..."
exit $exit_code

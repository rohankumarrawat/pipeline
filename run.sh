#!/usr/bin/env bash
# One command to set up and start everything: ./run.sh
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

pip install -q -r requirements.txt
python manage.py migrate --noinput
python manage.py recover_runs

echo ""
echo "  Open http://127.0.0.1:8000"
echo ""
# --noreload: the background runner lives in this process, so we don't want
# the auto-reloader starting a second copy.
python manage.py runserver 127.0.0.1:8000 --noreload

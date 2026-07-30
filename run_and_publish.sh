#!/bin/bash
set -e

# Runs hourly via cron; only proceeds at the target local shift-change hours.
# Self-checking in local time (rather than hardcoding UTC cron minutes) means
# this stays correct through DST and needs no changes if Alberta's time-change
# rules shift in the future.
TARGET_HOURS="05 12 17"
CURRENT_HOUR=$(TZ=America/Edmonton date +%H)
if [[ ! " $TARGET_HOURS " =~ " $CURRENT_HOUR " ]]; then
    exit 0
fi

cd /opt/airquality/github/edmonton_city_sitrep
source .venv/bin/activate
set -a
source /opt/airquality/config/intelligence.env
set +a

LOCKFILE="/opt/airquality/locks/edmonton_city_sitrep_git.lock"
mkdir -p "$(dirname "$LOCKFILE")"

(
  flock -w 120 200
  git fetch origin
  git pull --rebase origin main
) 200>"$LOCKFILE"

python run_demo.py

cp output/sitrep.pdf docs/sitrep.pdf

(
  flock -w 120 200

  git add docs/sitrep.pdf

  if git diff --cached --quiet; then
      echo "No changes to commit."
      exit 0
  fi

  git commit -m "chore: refresh sit-rep $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  for attempt in 1 2 3; do
      if git push origin main; then
          break
      fi
      echo "push rejected (attempt $attempt/3); rebasing onto latest and retrying..."
      git pull --rebase origin main
  done
) 200>"$LOCKFILE"

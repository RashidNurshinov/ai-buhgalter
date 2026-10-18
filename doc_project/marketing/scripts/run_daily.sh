#!/usr/bin/env bash
# Ежедневный прогон Дамира (крон 9:00): выгрузка МойСклад -> подборка кандидатов.
# Токены берутся из env: MOYSKLAD_FURNITURE_API_TOKEN, MOYSKLAD_GAMBIT_API_TOKEN.
set -euo pipefail
cd "$(dirname "$0")"
CACHE="${MKT_CACHE:-/tmp/mkt_cache}"
TODAY="${1:-$(date +%F)}"
python3 collect.py --cache "$CACHE" --today "$TODAY"
python3 candidates.py --cache "$CACHE" --today "$TODAY" --out ../output

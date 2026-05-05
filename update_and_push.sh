#!/usr/bin/env bash
# ФСЛ Dashboard — полный цикл обновления для cron на VPS
# Cron: 0 6 * * * /opt/fsl-dashboard/update_and_push.sh >> /var/log/fsl-dashboard.log 2>&1

set -e

cd "$(dirname "$0")"

echo ""
echo "===== $(date -u +'%Y-%m-%d %H:%M:%SZ') ====="

# Подгрузить env переменные (KIE_KEY, OPENROUTER_KEY, LPTRACKER_*, GOOGLE_SA_JSON)
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# 1. Подтянуть свежий manual-input.json если Виталий правил
git pull --rebase origin main || {
    echo "⚠ git pull --rebase упал, пробуем reset --hard"
    git fetch origin main
    git reset --hard origin/main
}

# 2. Сгенерить data.json (балансы API + manual-input)
python3 update.py

# 3. Закоммитить и запушить
./deploy.sh

echo "✓ done"

#!/usr/bin/env bash
# ФСЛ Dashboard — git push на GitHub Pages
# Используется update_and_push.sh на VPS И локально на маке Виталия

set -e

cd "$(dirname "$0")"

# Проверяем что есть изменения
if ! git diff --quiet data.json 2>/dev/null; then
    git add data.json
    git commit -m "auto: data.json refresh $(date -u +'%Y-%m-%d %H:%MZ')" || exit 0
    git push origin main
    echo "✓ pushed"
else
    echo "= no changes in data.json"
fi

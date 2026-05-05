# ФСЛ Дашборд для Айрата

Один URL для собственника: текущий день спринта май-июнь, прогресс к 70/80М, расходы из 1,9М, 14 каналов лидов, Kanban задач, балансы AI-инфры, открытые вопросы.

**Production URL:** https://volkovww-ui.github.io/fsl-dashboard/

## Архитектура

- `index.html` — vanilla HTML/CSS/JS, читает `data.json` через `fetch()`
- `data.json` — генерируется `update.py` из API + `manual-input.json` (НЕ редактировать руками)
- `manual-input.json` — **правит Виталий локально**, push в репо
- `update.py` — тянет балансы (kie.ai, OpenRouter), лиды (LP Tracker), пины (Sheets) → собирает `data.json`
- `deploy.sh` — `git add data.json && commit && push`
- `update_and_push.sh` — полный цикл для cron на VPS

## Локальный запуск

```bash
cd ~/Claude/projects/fsl-catalog/dashboard
python3 update.py
python3 -m http.server 8765
# открыть http://localhost:8765
```

## Креды (на маке)

- `~/Claude/credentials/kie-fsl-key.txt` — kie.ai API key
- `~/Claude/credentials/openrouter-fsl.txt` — OpenRouter API key
- `~/Claude/credentials/google-sa-fsl-pinterest.json` — Google Service Account для Sheets
- LP Tracker login/password — из env `LPTRACKER_LOGIN`, `LPTRACKER_PASSWORD` (default из `~/Claude/memory/credentials.md`)

## Деплой на VPS (cron 09:00 МСК)

```bash
ssh -i ~/.ssh/fsl_marketing_vps root@93.189.228.176

# на VPS:
mkdir -p /opt/fsl-dashboard && cd /opt/fsl-dashboard
git clone https://github.com/volkovww-ui/fsl-dashboard.git .

# креды (chmod 600 — критично):
mkdir -p ~/Claude/credentials
echo 'KIE_KEY=...' > /opt/fsl-dashboard/.env
echo 'OPENROUTER_KEY=...' >> /opt/fsl-dashboard/.env
echo 'LPTRACKER_LOGIN=dgy@5mas.ru' >> /opt/fsl-dashboard/.env
echo 'LPTRACKER_PASSWORD=Zeus2026' >> /opt/fsl-dashboard/.env
chmod 600 /opt/fsl-dashboard/.env

# Sheets SA — отдельным файлом
scp -i ~/.ssh/fsl_marketing_vps ~/Claude/credentials/google-sa-fsl-pinterest.json root@93.189.228.176:/opt/fsl-dashboard/sa.json

# Python deps:
pip3 install pyjwt cryptography

# Тест:
chmod +x update_and_push.sh deploy.sh
bash update_and_push.sh

# Cron (09:00 МСК = 06:00 UTC):
crontab -e
# добавить:
0 6 * * * /opt/fsl-dashboard/update_and_push.sh >> /var/log/fsl-dashboard.log 2>&1
```

## Включить GitHub Pages

```bash
gh repo create volkovww-ui/fsl-dashboard --public --description "ФСЛ дашборд спринта май-июнь"
git remote add origin https://github.com/volkovww-ui/fsl-dashboard.git
git push -u origin main
gh api -X POST /repos/volkovww-ui/fsl-dashboard/pages -f source[branch]=main -f source[path]=/ 2>/dev/null
```

URL появится через 1-2 мин: `https://volkovww-ui.github.io/fsl-dashboard/`

## Как Виталий правит данные

Открыть `manual-input.json`, изменить нужное (выручку, статус задач, найм, вопросы Айрату):

```bash
cd ~/Claude/projects/fsl-catalog/dashboard
$EDITOR manual-input.json
git commit -am "manual: <что изменил>" && git push
```

VPS подхватит при следующем cron-запуске (или сразу, если запустить `update_and_push.sh` руками).

## Что в data.json

```
meta             — sprint_day, days_to_review_*, updated_at_msk
sprint           — baseline, target_comfort/breakthrough, dates
progress         — pct_to_comfort, delta_rub
revenue          — sprint_total_rub, weeks[]
deals_closed     — число сделок закрытых
leads            — total_our_channels, lptracker_total
channels[]       — 14 каналов с прогнозом и фактом
tasks            — todo/doing/done списки
hires            — coordinator/mentor/video_editor/sergey/georgy
ai_content_counters — articles/pins/videos/letters/crm_returns
expenses_actual  — 5 категорий бюджета 1,9М
ai_infra         — kie.ai, openrouter, lptracker балансы
questions_for_airat — открытые решения
review_points    — 15.05 / 31.05 / 15.06 светофор
```

## TODO дыр (из самокритики плана)

- [ ] Heartbeat в `@volkovw_assist_bot` после успешного push
- [ ] Threshold-alert: kie.ai < $10, OpenRouter < $1 → TG
- [ ] Заменить хардкод LP Tracker login/password на `.env`
- [ ] Ротация `/var/log/fsl-dashboard.log` (logrotate)
- [ ] Подтвердить project_id LP Tracker для ФСЛ (177237 в credentials.md помечен как ЗЕВС)

#!/usr/bin/env python3
"""ФСЛ Dashboard — генератор data.json.

Источники:
  - manual-input.json (правит Виталий локально)
  - kie.ai balance (Bearer)
  - OpenRouter balance (Bearer)
  - LP Tracker leads (project 177237)
  - Google Sheets «Доска(отработано)» — счётчик опубликованных пинов

Запуск:
  python3 update.py            # обновить data.json
  python3 update.py --dry      # показать что получилось, не записывать

Креды берутся из переменных окружения с fallback на ~/Claude/credentials/:
  KIE_KEY                       или ~/Claude/credentials/kie-fsl-key.txt
  OPENROUTER_KEY                или ~/Claude/credentials/openrouter-fsl.txt
  LPTRACKER_LOGIN               или env LPTRACKER_LOGIN (default dgy@5mas.ru)
  LPTRACKER_PASSWORD            или env LPTRACKER_PASSWORD (default Zeus2026)
  GOOGLE_SA_JSON                или ~/Claude/credentials/google-sa-fsl-pinterest.json
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
CREDS_DIR = os.path.expanduser("~/Claude/credentials")
MANUAL_INPUT = os.path.join(ROOT, "manual-input.json")
DATA_OUT = os.path.join(ROOT, "data.json")

SHEET_ID = "1kMJLT3Cti6r4n3bKUIdoU6VSWPxqK6ToLUCA1BHOoDI"
PROCESSED_SHEET = "Доска(отработано)"
LPTRACKER_PROJECT_ID = 177237

MSK = timezone(timedelta(hours=3))


def _read_or_env(filename, env_key):
    env = os.environ.get(env_key)
    if env:
        return env.strip()
    path = os.path.join(CREDS_DIR, filename)
    if os.path.exists(path):
        return open(path).read().strip()
    return None


def _http(url, headers=None, data=None, method="GET", timeout=15):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="replace")
        return r.status, body


# ─── kie.ai ─────────────────────────────────────────────────────────────
def fetch_kie_balance():
    key = _read_or_env("kie-fsl-key.txt", "KIE_KEY")
    if not key:
        return {"status": "no_key", "balance_usd": None}
    try:
        _, body = _http(
            "https://api.kie.ai/api/v1/chat/credit",
            headers={"Authorization": f"Bearer {key}"},
        )
        j = json.loads(body)
        # kie.ai отдаёт {"code":200,"data":<число>} — где data это сам баланс в USD
        data = j.get("data")
        if isinstance(data, (int, float)):
            credit = data
        elif isinstance(data, dict):
            credit = data.get("credit") or data.get("balance")
        else:
            credit = j.get("credit") or j.get("balance")
        return {"status": "ok", "balance_usd": credit}
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        return {"status": "error", "balance_usd": None, "error": str(e)}


# ─── OpenRouter ─────────────────────────────────────────────────────────
def fetch_openrouter_balance():
    key = _read_or_env("openrouter-fsl.txt", "OPENROUTER_KEY")
    if not key:
        return {"status": "no_key", "balance_usd": None}
    try:
        _, body = _http(
            "https://openrouter.ai/api/v1/credits",
            headers={"Authorization": f"Bearer {key}"},
        )
        j = json.loads(body)
        d = j.get("data") or {}
        total = d.get("total_credits", 0)
        used = d.get("total_usage", 0)
        return {"status": "ok", "balance_usd": round(total - used, 4), "total": total, "used": used}
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        return {"status": "error", "balance_usd": None, "error": str(e)}


# ─── LP Tracker ─────────────────────────────────────────────────────────
def fetch_lptracker_leads():
    login = os.environ.get("LPTRACKER_LOGIN", "dgy@5mas.ru")
    password = os.environ.get("LPTRACKER_PASSWORD", "Zeus2026")
    try:
        # auth: POST /login {login, password, service, version}
        body = json.dumps({
            "login": login, "password": password,
            "service": "lptracker", "version": "1.0",
        }).encode()
        _, resp = _http(
            "https://direct.lptracker.ru/login",
            headers={"Content-Type": "application/json"},
            data=body, method="POST",
        )
        token = (json.loads(resp).get("result") or {}).get("token")
        if not token:
            return {"status": "auth_failed", "leads_total": None, "raw": resp[:200]}
        # leads: GET /lead/{project_id}/list
        _, leads_resp = _http(
            f"https://direct.lptracker.ru/lead/{LPTRACKER_PROJECT_ID}/list",
            headers={"token": token},
        )
        leads = (json.loads(leads_resp).get("result") or [])
        return {"status": "ok", "leads_total": len(leads) if isinstance(leads, list) else None}
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        return {"status": "error", "leads_total": None, "error": str(e)}


# ─── Google Sheets — счётчик пинов ──────────────────────────────────────
def fetch_pins_count():
    sa_path = os.environ.get("GOOGLE_SA_JSON") or os.path.join(CREDS_DIR, "google-sa-fsl-pinterest.json")
    if not os.path.exists(sa_path):
        return {"status": "no_sa", "pins_count": None}
    try:
        import jwt as pyjwt  # из pin_e2e.py — стандартный путь
        sa = json.load(open(sa_path))
        now = int(time.time())
        claims = {
            "iss": sa["client_email"],
            "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
            "aud": "https://oauth2.googleapis.com/token",
            "exp": now + 3600, "iat": now,
        }
        signed = pyjwt.encode(claims, sa["private_key"], algorithm="RS256")
        body = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed,
        }).encode()
        _, tok_resp = _http("https://oauth2.googleapis.com/token", data=body, method="POST")
        tok = json.loads(tok_resp)["access_token"]
        rng = urllib.parse.quote(f"{PROCESSED_SHEET}!A:A")
        _, vals_resp = _http(
            f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{rng}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        rows = json.loads(vals_resp).get("values", [])
        # вычитаем header
        return {"status": "ok", "pins_count": max(0, len(rows) - 1)}
    except Exception as e:
        return {"status": "error", "pins_count": None, "error": str(e)}


# ─── Сборка data.json ───────────────────────────────────────────────────
def compute_sprint_meta(manual):
    today = datetime.now(MSK).date()
    start = datetime.fromisoformat(manual["sprint"]["start_date"]).date()
    end = datetime.fromisoformat(manual["sprint"]["end_date"]).date()
    total_days = (end - start).days + 1
    day_n = max(0, (today - start).days + 1)
    day_n = min(day_n, total_days)
    review_15 = datetime.fromisoformat("2026-05-15").date()
    review_31 = datetime.fromisoformat("2026-05-31").date()
    review_jun15 = datetime.fromisoformat("2026-06-15").date()

    def days_to(d):
        return (d - today).days

    return {
        "today_iso": today.isoformat(),
        "today_human": today.strftime("%d.%m.%Y"),
        "sprint_day": day_n,
        "sprint_total_days": total_days,
        "days_to_review_15may": days_to(review_15),
        "days_to_review_31may": days_to(review_31),
        "days_to_review_15jun": days_to(review_jun15),
    }


def compute_progress(manual):
    sp = manual["sprint"]
    rev = manual["revenue"]
    revenue = rev["sprint_total_rub"]
    # Прогресс — это накопительная выручка спринта к цели 70М/80М (а не дельта от baseline,
    # которая отрицательна на старте). Дельта вычисляется отдельно и показывается только
    # когда revenue >= baseline.
    pct_to_comfort = round(100 * revenue / sp["target_comfort_rub"], 1) if sp["target_comfort_rub"] else 0
    pct_to_breakthrough = round(100 * revenue / sp["target_breakthrough_rub"], 1) if sp["target_breakthrough_rub"] else 0
    delta_above_baseline = max(0, revenue - sp["baseline_rub"])
    return {
        "revenue_total_rub": revenue,
        "delta_above_baseline_rub": delta_above_baseline,
        "pct_to_comfort": pct_to_comfort,
        "pct_to_breakthrough": pct_to_breakthrough,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="не писать data.json, показать в stdout")
    args = ap.parse_args()

    if not os.path.exists(MANUAL_INPUT):
        print(f"ERROR: {MANUAL_INPUT} не найден", file=sys.stderr)
        sys.exit(1)
    manual = json.load(open(MANUAL_INPUT))

    print("→ kie.ai balance...", flush=True)
    kie = fetch_kie_balance()
    print(f"   {kie.get('status')}: {kie.get('balance_usd')}", flush=True)

    print("→ OpenRouter balance...", flush=True)
    or_ = fetch_openrouter_balance()
    print(f"   {or_.get('status')}: {or_.get('balance_usd')}", flush=True)

    print("→ LP Tracker leads (project 177237)...", flush=True)
    lp = fetch_lptracker_leads()
    print(f"   {lp.get('status')}: {lp.get('leads_total')}", flush=True)

    print("→ Pinterest pins count (Sheets)...", flush=True)
    pins = fetch_pins_count()
    print(f"   {pins.get('status')}: {pins.get('pins_count')}", flush=True)

    meta = compute_sprint_meta(manual)
    progress = compute_progress(manual)

    # счётчик пинов: auto если есть, иначе manual
    if pins.get("pins_count") is not None:
        manual["ai_content_counters"]["pins_published"] = pins["pins_count"]

    # лиды LP Tracker → если есть, обновляем total_our_channels
    if lp.get("leads_total") is not None:
        manual["leads"]["lptracker_total"] = lp["leads_total"]

    data = {
        "meta": {
            **meta,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "updated_at_msk": datetime.now(MSK).strftime("%Y-%m-%d %H:%M МСК"),
            "manual_input_edited": manual.get("_last_edited"),
        },
        "sprint": manual["sprint"],
        "progress": progress,
        "revenue": manual["revenue"],
        "deals_closed": manual["deals_closed"],
        "leads": manual["leads"],
        "channels": manual["channels"],
        "tasks": manual["tasks"],
        "hires": manual["hires"],
        "ai_content_counters": manual["ai_content_counters"],
        "expenses_actual": manual["expenses_actual"],
        "questions_for_airat": manual["questions_for_airat"],
        "review_points": manual["review_points"],
        "ai_infra": {
            "kie_ai": kie,
            "openrouter": or_,
            "lptracker": {"status": lp.get("status"), "leads_total": lp.get("leads_total")},
        },
    }

    out = json.dumps(data, ensure_ascii=False, indent=2)
    if args.dry:
        print(out)
    else:
        with open(DATA_OUT, "w") as f:
            f.write(out)
        print(f"✓ data.json записан ({len(out)} байт)")


if __name__ == "__main__":
    main()

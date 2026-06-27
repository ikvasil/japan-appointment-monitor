import os, json, requests
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime, timezone

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in open(env_path):
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k] = v

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]
BASE_URL = "https://eojqbooking.rsvsys.jp"
CALENDAR_URL = f"{BASE_URL}/reservations/calendar"
AJAX_URL = f"{BASE_URL}/ajax/reservations/calendar"
STATE = "/home/japan_monitor/last_state.json"

def telegram(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT, "text": msg})

def get_csrf_and_session():
    session = requests.Session()
    r = session.get(CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    csrf = None
    token_fields = None
    for inp in soup.find_all("input", {"name": "_csrfToken"}):
        csrf = inp.get("value")
    for inp in soup.find_all("input", {"name": "_Token[fields]"}):
        token_fields = inp.get("value")
    return session, csrf, token_fields

def get_slots_for_month(session, csrf, token_fields, date_str):
    try:
        data = {
            "_method": "POST",
            "_csrfToken": csrf,
            "event": "1",
            "plan": "1",
            "date": date_str,
            "disp_type": "month",
            "_Token[fields]": token_fields,
            "_Token[unlocked]": "",
            "search": "exec"
        }
        r = session.post(AJAX_URL, data=data, headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": CALENDAR_URL}, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        dates = []
        for td in soup.find_all("td"):
            img = td.find("img")
            if img and "icon_circle" in img.get("src", ""):
                t = td.get_text(strip=True)
                if t:
                    dates.append(f"{date_str[:7]}/{t}")
        return dates
    except Exception as e:
        telegram(f"Error checking {date_str}: {e}")
        return []

def get_all_slots():
    try:
        now = datetime.now(timezone.utc)
        session, csrf, token_fields = get_csrf_and_session()
        if not csrf:
            telegram("Could not get CSRF token")
            return None
        months = []
        for i in range(3):
            month = now.month + i
            year = now.year
            if month > 12:
                month -= 12
                year += 1
            date_str = f"{year}/{month:02d}/01"
            slots = get_slots_for_month(session, csrf, token_fields, date_str)
            months.extend(slots)
        return months
    except Exception as e:
        telegram(f"Monitor error: {e}")
        return None

def load():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"dates": [], "hour": -1, "checks": 0, "found": False, "found_time": None}

def save(d):
    json.dump(d, open(STATE, "w"))

def main():
    now = datetime.now(timezone.utc)
    hour = now.hour
    time_str = now.strftime("%d %b %Y %H:%M UTC")
    slots = get_all_slots()
    if slots is None:
        return
    s = load()
    s["checks"] += 1
    new = [d for d in slots if d not in s["dates"]]
    if new:
        msg = "JAPAN EMBASSY - New slots open!\n\n"
        for d in new:
            msg += f"Date: {d}\n"
        msg += f"\nBook: {CALENDAR_URL}"
        telegram(msg)
        s["found"] = True
        s["found_time"] = time_str
    if hour != s["hour"]:
        hl = now.strftime("%d %b %Y %H:00 UTC")
        if s["found"]:
            out = f"Hourly Summary {hl}\n\nSLOT FOUND at {s['found_time']}!\nChecks: {s['checks']}\nRunning OK"
        elif slots:
            out = f"Hourly Summary {hl}\n\nSlots available: {', '.join(slots)}\nChecks: {s['checks']}\nRunning OK"
        else:
            out = f"Hourly Summary {hl}\n\nNo slots\nChecks: {s['checks']}\nRunning OK"
        telegram(out)
        s["hour"] = hour
        s["checks"] = 0
        s["found"] = False
        s["found_time"] = None
    s["dates"] = slots
    save(s)

main()

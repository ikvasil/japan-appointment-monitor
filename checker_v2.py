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
CALENDAR_URL = BASE_URL + "/reservations/calendar"
AJAX_URL = BASE_URL + "/ajax/reservations/calendar"
STATE = "/home/japan_monitor/last_state.json"

def telegram(msg):
    requests.post("https://api.telegram.org/bot" + TOKEN + "/sendMessage", json={"chat_id": CHAT, "text": msg})

def get_all_slots():
    try:
        session = requests.Session()
        r = session.get(CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        csrf = None
        token_fields = None
        for inp in soup.find_all("input", {"name": "_csrfToken"}):
            csrf = inp.get("value")
        for inp in soup.find_all("input", {"name": "_Token[fields]"}):
            token_fields = inp.get("value")
        if not csrf:
            telegram("Monitor error: Could not get CSRF token")
            return None
        now = datetime.now(timezone.utc)
        all_slots = []
        for i in range(3):
            month = now.month + i
            year = now.year
            if month > 12:
                month -= 12
                year += 1
            date_str = str(year) + "/" + str(month).zfill(2) + "/01"
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
            r2 = session.post(AJAX_URL, data=data, headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": CALENDAR_URL}, timeout=30)
            data2 = json.loads(r2.text)
            soup2 = BeautifulSoup(data2["html"], "html.parser")
            for td in soup2.find_all("td"):
                img = td.find("img")
                if img and "icon_circle" in img.get("src", ""):
                    t = td.get_text(strip=True)
                    if t:
                        all_slots.append(str(year) + "/" + str(month).zfill(2) + "/" + t.zfill(2))
        return all_slots
    except Exception as e:
        telegram("Monitor error: " + str(e))
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
            msg += "Date: " + d + "\n"
        msg += "\nBook now: " + CALENDAR_URL
        telegram(msg)
        s["found"] = True
        s["found_time"] = time_str
   if hour != s["hour"]:
        hl = now.strftime("%d %b %Y %H:00 UTC")
        if s["found"]:
            out = "Hourly Summary " + hl + "\n\nSLOT FOUND at " + str(s["found_time"]) + "!\nChecks: " + str(s["checks"]) + "\nRunning OK"
        elif slots:
            out = "Hourly Summary " + hl + "\n\nSlots available: " + ", ".join(slots) + "\nChecks: " + str(s["checks"]) + "\nRunning OK"
        else:
            out = "Hourly Summary " + hl + "\n\nNo slots\nChecks: " + str(s["checks"]) + "\nRunning OK"
        telegram(out)
        s["hour"] = hour
        s["checks"] = 0
        s["found"] = False
        s["found_time"] = None
    s["dates"] = slots
    save(s)

main()

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CALENDAR_URL = "https://eojqbooking.rsvsys.jp/reservations/calendar"
STATE_FILE = "last_state.json"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

def check_slots():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(CALENDAR_URL, headers=headers, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")

        available_dates = []
        cells = soup.find_all("td")

        for cell in cells:
            img = cell.find("img")
            if img and "icon_circle" in img.get("src", ""):
                date_text = cell.get_text(strip=True)
                if date_text:
                    available_dates.append(date_text)

        return available_dates

    except Exception as e:
        send_telegram(f"⚠️ Monitor error: {str(e)}")
        return None

def load_last_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "available_dates": [],
        "last_summary_hour": -1,
        "checks_since_summary": 0,
        "slot_found_since_summary": False,
        "slot_found_time": None
    }

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def main():
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    current_time_str = now.strftime("%d %b %Y %H:%M UTC")

    current_slots = check_slots()

    if current_slots is None:
        return

    last_state = load_last_state()
    last_slots = last_state.get("available_dates", [])
    last_summary_hour = last_state.get("last_summary_hour", -1)
    checks_since_summary = last_state.get("checks_since_summary", 0)
    slot_found_since_summary = last_state.get("slot_found_since_summary", False)
    slot_found_time = last_state.get("slot_found_time", None)

    checks_since_summary += 1

    # Check for new slots — send INSTANT alert
    new_slots = [d for d in current_slots if d not in last_slots]

    if new_slots:
        message = (
            "🚨 <b>JAPAN EMBASSY APPOINTMENT ALERT</b> 🚨\n\n"
            "✅ New slots just opened:\n"
        )
        for date in new_slots:
            message += f"  📅 {date}\n"
        message += f"\n👉 Book now: {CALENDAR_URL}"
        send_telegram(message)
        slot_found_since_summary = True
        slot_found_time = current_time_str

    # Send hourly summary once per hour
    if current_hour != last_summary_hour:
        hour_label = now.strftime("%d %b %Y %H:00 UTC")

        if slot_found_since_summary:
            summary = (
                f"📊 <b>Hourly Summary — {hour_label}</b>\n\n"
                f"🚨 SLOT WAS FOUND at {slot_found_time}!\n"
                f"Checks this hour: {checks_since_summary}\n"
                f"Monitor is running normally ✅"
            )
        elif current_slots:
            summary = (
                f"📊 <b>Hourly Summary — {hour_label}</b>\n\n"
                f"✅ Slots currently available:\n"
            )
            for date in current_slots:
                summary += f"  📅 {date}\n"
            summary += f"\nChecks this hour: {checks_since_summary}\nMonitor is running normally ✅"
        else:
            summary = (
                f"📊 <b>Hourly Summary — {hour_label}</b>\n\n"
                f"🔴 No slots available\n"
                f"Checks this hour: {checks_since_summary}\n"
                f"Monitor is running normally ✅"
            )

        send_telegram(summary)

        # Reset hourly counters
        last_summary_hour = current_hour
        checks_since_summary = 0
        slot_found_since_summary = False
        slot_found_time = None

    save_state({
        "available_dates": current_slots,
        "last_summary_hour": last_summary_hour,
        "checks_since_summary": checks_since_summary,
        "slot_found_since_summary": slot_found_since_summary,
        "slot_found_time": slot_found_time
    })

if __name__ == "__main__":
    main()

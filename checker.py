import requests
from bs4 import BeautifulSoup
import json
import os

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

        # Find all available slots (icon_circle = available)
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
    return {"available_dates": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def main():
    current_slots = check_slots()

    if current_slots is None:
        return  # Error already sent via Telegram

    last_state = load_last_state()
    last_slots = last_state.get("available_dates", [])

    # Check if anything changed
    new_slots = [d for d in current_slots if d not in last_slots]
    gone_slots = [d for d in last_slots if d not in current_slots]

    if new_slots:
        message = (
            "🚨 <b>JAPAN EMBASSY APPOINTMENT ALERT</b> 🚨\n\n"
            "✅ New slots just opened:\n"
        )
        for date in new_slots:
            message += f"  📅 {date}\n"
        message += f"\n👉 Book now: {CALENDAR_URL}"
        send_telegram(message)

    if gone_slots and not new_slots:
        # Optional: notify if slots disappeared
        pass

    if not current_slots and last_slots:
        send_telegram("ℹ️ Japan Embassy: All slots are now fully booked.")

    # Save current state
    save_state({"available_dates": current_slots})

if __name__ == "__main__":
    main()

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TICKET_URL = "https://ticketing.colosseo.it/en/eventi/full-experience-sotterranei-e-arena/"
NTFY_TOPIC = os.environ["NTFY_TOPIC"]

TARGET_DATES = [
    "2026-06-22", "2026-06-23", "2026-06-24",
    "2026-06-25", "2026-06-26", "2026-06-27", "2026-06-28",
]

SOLD_OUT_KEYWORDS = ["sold out", "unavailable", "esaurito", "non disponibile", "no tickets"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def check_tickets():
    try:
        resp = requests.get(TICKET_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Request failed: {e}")
        return

    html = resp.text
    available = []

    for target in TARGET_DATES:
        dt = datetime.strptime(target, "%Y-%m-%d")
        # Check multiple date formats the site may use
        patterns = [
            target,                      # 2026-06-22
            dt.strftime("%d/%m/%Y"),     # 22/06/2026
            dt.strftime("%d-%m-%Y"),     # 22-06-2026
            dt.strftime("%B %d, %Y"),    # June 22, 2026
            dt.strftime("%d %B %Y"),     # 22 June 2026
        ]
        for pattern in patterns:
            idx = html.find(pattern)
            if idx == -1:
                continue
            # Grab surrounding context to check for sold-out markers
            context = html[max(0, idx - 300):idx + 300].lower()
            if not any(kw in context for kw in SOLD_OUT_KEYWORDS):
                available.append(target)
            break

    if available:
        notify(available)
    else:
        print(f"[{datetime.now()}] No availability for target dates.")


def notify(dates):
    msg = f"Book now: {TICKET_URL}"
    print(f"[{datetime.now()}] AVAILABLE: {dates}")
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=msg.encode("utf-8"),
            headers={
                "Title": f"Colosseum tickets open: {', '.join(dates)}",
                "Priority": "urgent",
                "Tags": "rotating_light,ticket",
            },
            timeout=10,
        )
        print("Notification sent.")
    except requests.RequestException as e:
        print(f"Notification failed: {e}")


if __name__ == "__main__":
    check_tickets()

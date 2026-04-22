import asyncio
import json
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from playwright.async_api import async_playwright

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DATES = [
    "2026-06-22", "2026-06-23", "2026-06-24",
    "2026-06-25", "2026-06-26", "2026-06-27", "2026-06-28",
]

TICKETS = {
    "🏛️  Underground & Arena":   "full-experience-sotterranei-e-arena",
    "⚔️  Full Experience Arena":  "full-experience",
    "🔝 Full Experience Attic":  "full-experience-attico",
    "🎟️  24h Colosseum":         "24h-colosseo-foro-romano-palatino",
}

GMAIL      = os.environ["GMAIL"]
APP_PW     = os.environ["GMAIL_APP_PW"]
BASE       = "https://ticketing.colosseo.it/en/eventi/"
UTC_OFFSET = timedelta(hours=2)

PAUZE_TUSSEN_TICKETS = 30
PAUZE_TUSSEN_MAANDEN = 15
PAUZE_VOOR_24H       = 60
# ─────────────────────────────────────────────────────────────────────────────

XHR_SCRIPT = """
    window.__calendarData = null;
    const origOpen = XMLHttpRequest.prototype.open;
    const origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url, ...args) {
        this.__url = url;
        return origOpen.call(this, method, url, ...args);
    };
    XMLHttpRequest.prototype.send = function(...args) {
        this.addEventListener('load', function() {
            if (this.__url && this.__url.includes('calendars_month')) {
                window.__calendarData = this.responseText;
            }
        });
        return origSend.call(this, ...args);
    };
"""

BROWSER_ARGS = {
    "headless": True,
    "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
}

CONTEXT_ARGS = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "locale": "en-US",
    "viewport": {"width": 1280, "height": 800},
}

STEALTH = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3]});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
    window.chrome = {runtime: {}};
"""


def groepeer_per_maand(dates):
    maanden = {}
    for datum in dates:
        maand = datum[:7]
        maanden.setdefault(maand, []).append(datum)
    return maanden


def verwerk_slots(slots, datums):
    resultaten = {}
    for datum in datums:
        vrije_slots = []
        for s in slots:
            if datum in s.get("startDateTime", "") and s.get("capacity", 0) > 0:
                utc_tijd     = datetime.strptime(s["startDateTime"], "%Y-%m-%dT%H:%M:%SZ")
                italie_tijd  = utc_tijd + UTC_OFFSET
                vrije_slots.append(f"  {italie_tijd.strftime('%H:%M')} — {s['capacity']} plaatsen")
        vrije_totaal = sum(
            s.get("capacity", 0) for s in slots
            if datum in s.get("startDateTime", "")
        )
        resultaten[datum] = (vrije_totaal, vrije_slots)
    return resultaten


def stuur_mail(hits):
    regels = [f"Controle: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"]
    for h in hits:
        regels += [
            "─" * 40,
            f"Ticket: {h['ticket']}",
            f"Datum:  {h['datum']}",
            f"Totaal: {h['vrije']} plaatsen",
            "Tijdsloten:",
            *h["slots"],
            f"Boek nu: {h['url']}",
            "",
        ]

    body      = "\n".join(regels)
    onderwerp = f"🏛️ Colosseum beschikbaar — {len(hits)} slot(s) gevonden"

    msg           = MIMEText(body)
    msg["From"]   = GMAIL
    msg["To"]     = GMAIL
    msg["Subject"] = onderwerp

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL, APP_PW)
            s.send_message(msg)
        print(f"  📧 Mail verstuurd! ({len(hits)} slot(s))")
    except Exception as e:
        print(f"  📧 E-mail mislukt: {e}")


async def haal_data_voor_ticket(playwright, slug, maanden):
    browser = await playwright.chromium.launch(**BROWSER_ARGS)
    context = await browser.new_context(**CONTEXT_ARGS)
    await context.add_init_script(STEALTH)
    page    = await context.new_page()
    resultaten = {}

    try:
        for maand, datums in maanden.items():
            await page.add_init_script(XHR_SCRIPT)
            url = f"{BASE}{slug}/?date={datums[0]}"
            try:
                await page.goto(url, timeout=60000, wait_until="networkidle")
                raw = None
                for _ in range(20):
                    await asyncio.sleep(1)
                    raw = await page.evaluate("window.__calendarData")
                    if raw and not raw.strip().startswith("<!"):
                        break
                resultaten[maand] = (raw, datums)
            except Exception as e:
                print(f"  ⚠️  Fout bij laden {slug} / {maand}: {e}")
                resultaten[maand] = (None, datums)
            await asyncio.sleep(PAUZE_TUSSEN_MAANDEN)
    finally:
        await browser.close()

    return resultaten


async def run():
    print("=" * 55)
    print("  🏛️  Colosseum Ticket Checker")
    print(f"  📅  {DATES[0]} t/m {DATES[-1]}")
    print("=" * 55)

    maanden = groepeer_per_maand(DATES)
    hits    = []

    async with async_playwright() as playwright:
        for ticket_naam, slug in TICKETS.items():
            if slug == "24h-colosseo-foro-romano-palatino":
                print(f"  ⏳ Extra pauze voor 24h ({PAUZE_VOOR_24H}s)...")
                await asyncio.sleep(PAUZE_VOOR_24H)

            maand_data = await haal_data_voor_ticket(playwright, slug, maanden)

            for maand, (raw, datums) in maand_data.items():
                if raw is None:
                    for datum in datums:
                        print(f"  {ticket_naam[:22]:<22} {datum}  ❓")
                    continue
                try:
                    data       = json.loads(raw)
                    slots      = data.get("data", [])
                    resultaten = verwerk_slots(slots, datums)
                    for datum, (vrije, slots_list) in resultaten.items():
                        if vrije > 0:
                            url = f"{BASE}{slug}/?date={datum}"
                            print(f"  {ticket_naam[:22]:<22} {datum}  ✅ {vrije} plaatsen!")
                            for slot in slots_list:
                                print(slot)
                            hits.append({
                                "ticket": ticket_naam,
                                "datum":  datum,
                                "url":    url,
                                "vrije":  vrije,
                                "slots":  slots_list,
                            })
                        else:
                            print(f"  {ticket_naam[:22]:<22} {datum}  ❌")
                except Exception as e:
                    for datum in datums:
                        print(f"  {ticket_naam[:22]:<22} {datum}  ⚠️ parse fout: {e}")

            await asyncio.sleep(PAUZE_TUSSEN_TICKETS)

    if hits:
        print(f"\n  📊 {len(hits)} beschikbare slot(s) gevonden — mail versturen...")
        stuur_mail(hits)
    else:
        print("\n  ✓ Geen beschikbaarheid gevonden.")


if __name__ == "__main__":
    asyncio.run(run())

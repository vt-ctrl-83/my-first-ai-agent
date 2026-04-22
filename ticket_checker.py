import asyncio
import json
import os
import requests
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DATES = [
    # Test: mei 2026 (dichtbij, makkelijk te verifiëren)
    "2026-05-01", "2026-05-02", "2026-05-03",
    # Target: juni week 22-28
    "2026-06-22", "2026-06-23", "2026-06-24",
    "2026-06-25", "2026-06-26", "2026-06-27", "2026-06-28",
]

TICKETS = {
    "🏛️  Underground & Arena":   "full-experience-sotterranei-e-arena",
    "⚔️  Full Experience Arena":  "full-experience",
    "🔝 Full Experience Attic":  "full-experience-attico",
    "🎟️  24h Colosseum":         "24h-colosseo-foro-romano-palatino",
}

NTFY_TOPIC  = os.environ["NTFY_TOPIC"]
STATE_FILE  = "state.json"
BASE        = "https://ticketing.colosseo.it/en/eventi/"
UTC_OFFSET  = timedelta(hours=2)

PAUZE_TUSSEN_TICKETS = 30
PAUZE_TUSSEN_MAANDEN = 15
PAUZE_VOOR_24H       = 60
# ─────────────────────────────────────────────────────────────────────────────

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


# ─── STATE ───────────────────────────────────────────────────────────────────

def laad_staat():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return {tuple(k.split("|")): v for k, v in json.load(f).items()}
    return {}


def sla_staat_op(hits):
    staat = {f"{h['ticket']}|{h['datum']}": h["vrije"] for h in hits}
    with open(STATE_FILE, "w") as f:
        json.dump(staat, f)


def bereken_delta(hits_nu, vorige_staat):
    nu        = {(h["ticket"], h["datum"]): h for h in hits_nu}
    nieuw     = [h for k, h in nu.items() if k not in vorige_staat]
    meer      = [h for k, h in nu.items() if k in vorige_staat and h["vrije"] > vorige_staat[k]]
    verdwenen = [k for k in vorige_staat if k not in nu]
    return nieuw, meer, verdwenen


# ─── NOTIFICATION ────────────────────────────────────────────────────────────

def stuur_notificatie(hits, label, priority="urgent", tags="rotating_light,ticket"):
    for h in hits:
        tijden  = ", ".join(s.strip().split("—")[0].strip() for s in h["slots"]) or "?"
        bericht = f"{h['datum']} · {h['vrije']} plaatsen · {tijden}\n{h['url']}"
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=bericht.encode("utf-8"),
                headers={
                    "Title":    f"{label}: {h['ticket'].strip()}",
                    "Priority": priority,
                    "Tags":     tags,
                },
                timeout=10,
            )
            print(f"  📱 [{label}] {h['ticket'].strip()} {h['datum']}")
        except Exception as e:
            print(f"  📱 Notificatie mislukt: {e}")


def stuur_verdwenen(verdwenen_keys):
    for ticket, datum in verdwenen_keys:
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data=f"{ticket.strip()} op {datum} is niet meer beschikbaar.".encode("utf-8"),
                headers={
                    "Title":    f"❌ Weg: {ticket.strip()}",
                    "Priority": "default",
                    "Tags":     "x",
                },
                timeout=10,
            )
            print(f"  📱 [Weg] {ticket.strip()} {datum}")
        except Exception as e:
            print(f"  📱 Notificatie mislukt: {e}")


# ─── SCRAPER ─────────────────────────────────────────────────────────────────

def groepeer_per_maand(dates):
    maanden = {}
    for datum in dates:
        maanden.setdefault(datum[:7], []).append(datum)
    return maanden


def verwerk_slots(slots, datums):
    resultaten = {}
    for datum in datums:
        vrije_slots = []
        for s in slots:
            if datum in s.get("startDateTime", "") and s.get("capacity", 0) > 0:
                utc_tijd    = datetime.strptime(s["startDateTime"], "%Y-%m-%dT%H:%M:%SZ")
                italie_tijd = utc_tijd + UTC_OFFSET
                vrije_slots.append(f"  {italie_tijd.strftime('%H:%M')} — {s['capacity']} plaatsen")
        vrije_totaal = sum(
            s.get("capacity", 0) for s in slots
            if datum in s.get("startDateTime", "")
        )
        resultaten[datum] = (vrije_totaal, vrije_slots)
    return resultaten


async def haal_data_voor_ticket(playwright, slug, maanden):
    browser = await playwright.chromium.launch(**BROWSER_ARGS)
    context = await browser.new_context(**CONTEXT_ARGS)
    await context.add_init_script(STEALTH)
    page    = await context.new_page()
    resultaten = {}

    try:
        for maand, datums in maanden.items():
            url = f"{BASE}{slug}/?date={datums[0]}"
            gevangen = []  # (response_url, text)

            async def vang_response(response):
                content_type = response.headers.get("content-type", "")
                if "json" in content_type and response.status == 200:
                    try:
                        tekst = await response.text()
                        gevangen.append((response.url, tekst))
                        print(f"  🔍 JSON: {response.url}")
                    except Exception:
                        pass

            page.on("response", vang_response)
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(8)  # wacht op lazy API-calls
                await page.evaluate("window.scrollTo(0, 500)")
                await asyncio.sleep(3)
            except Exception as e:
                print(f"  ⚠️  Pagina laad-fout {slug} / {maand}: {e}")
            page.remove_listener("response", vang_response)

            # Screenshot als artifact voor debugging
            screenshot = f"debug_{slug[:25]}_{maand}.png"
            await page.screenshot(path=screenshot)
            print(f"  📸 Screenshot: {screenshot}")

            # Zoek kalenderdata op basis van bekende URL-patronen
            KALENDER_PATRONEN = ["calendar", "slot", "availability", "month", "event"]
            raw = None
            for resp_url, tekst in gevangen:
                if any(p in resp_url.lower() for p in KALENDER_PATRONEN):
                    raw = tekst
                    print(f"  ✔ Kalender-URL gevonden: {resp_url}")
                    break

            if raw is None:
                if gevangen:
                    print(f"  ℹ️  Alle JSON-URLs voor {slug} / {maand}:")
                    for resp_url, _ in gevangen:
                        print(f"       {resp_url}")
                else:
                    print(f"  ⚠️  Geen enkele JSON-response voor {slug} / {maand}")

            resultaten[maand] = (raw, datums)
            await asyncio.sleep(PAUZE_TUSSEN_MAANDEN)
    finally:
        await browser.close()

    return resultaten


# ─── MAIN ────────────────────────────────────────────────────────────────────

async def run():
    print("=" * 55)
    print("  🏛️  Colosseum Ticket Checker")
    print(f"  📅  {DATES[0]} t/m {DATES[-1]}")
    print("=" * 55)

    vorige_staat = laad_staat()
    print(f"  📂 Vorige staat: {len(vorige_staat)} slot(s) bekend\n")

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

    nieuw, meer, verdwenen = bereken_delta(hits, vorige_staat)
    print(f"\n  📊 Delta: {len(nieuw)} nieuw · {len(meer)} meer plaatsen · {len(verdwenen)} weg")

    if nieuw:
        stuur_notificatie(nieuw, "🆕 Nieuw")
    if meer:
        stuur_notificatie(meer, "📈 Meer plaatsen", priority="high", tags="chart_increasing")
    if verdwenen:
        stuur_verdwenen(verdwenen)
    if not nieuw and not meer and not verdwenen:
        print("  ✓ Geen wijzigingen.")

    sla_staat_op(hits)
    print("  💾 Staat opgeslagen.")


if __name__ == "__main__":
    asyncio.run(run())

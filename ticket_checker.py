import json
import os
import requests
from datetime import datetime, timedelta

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TARGET_DATES = [
    "2026-06-22", "2026-06-23", "2026-06-24",
    "2026-06-25", "2026-06-26", "2026-06-27", "2026-06-28",
]

TICKETS = {
    "🏛️  Underground & Arena":   225,
    "⚔️  Full Experience Arena":  76,
    "🔝 Full Experience Attic":  133,
    "🎟️  24h Colosseum":         35,
}

SLUGS = {
    "🏛️  Underground & Arena":   "full-experience-sotterranei-e-arena",
    "⚔️  Full Experience Arena":  "full-experience",
    "🔝 Full Experience Attic":  "full-experience-attico",
    "🎟️  24h Colosseum":         "24h-colosseo-foro-romano-palatino",
}

API_URL    = "https://ticketing.colosseo.it/mtajax/calendars_month"
BASE_URL   = "https://ticketing.colosseo.it/en/eventi/"
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
STATE_FILE = "state.json"
UTC_OFFSET = timedelta(hours=2)

HEADERS = {
    "accept":           "*/*",
    "accept-language":  "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type":     "application/x-www-form-urlencoded; charset=UTF-8",
    "origin":           "https://ticketing.colosseo.it",
    "referer":          "https://ticketing.colosseo.it/en/eventi/",
    "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}
# ─────────────────────────────────────────────────────────────────────────────


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


def haal_kalender(page_id, jaar, maand):
    try:
        resp = requests.post(
            API_URL,
            data={
                "action": "midaabc_calendars_month",
                "page":   page_id,
                "year":   jaar,
                "month":  maand,
            },
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        cache = resp.headers.get("x-octofence-cache", "?")
        print(f"  → page={page_id} {jaar}-{maand:02d}  HTTP {resp.status_code}  cache={cache}")
        return resp.json()
    except Exception as e:
        print(f"  ⚠️ API fout (page={page_id}, {jaar}-{maand:02d}): {e}")
        return None


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


def groepeer_per_maand(dates):
    maanden = {}
    for datum in dates:
        maanden.setdefault(datum[:7], []).append(datum)
    return maanden


def run():
    print("=" * 55)
    print("  🏛️  Colosseum Ticket Checker")
    print(f"  📅  {TARGET_DATES[0]} t/m {TARGET_DATES[-1]}")
    print("=" * 55)

    vorige_staat = laad_staat()
    print(f"  📂 Vorige staat: {len(vorige_staat)} slot(s) bekend\n")

    maanden = groepeer_per_maand(TARGET_DATES)
    hits    = []

    for ticket_naam, page_id in TICKETS.items():
        for maand_str, datums in maanden.items():
            jaar, m = maand_str.split("-")
            data    = haal_kalender(page_id, int(jaar), int(m))

            if data is None:
                for datum in datums:
                    print(f"  {ticket_naam[:22]:<22} {datum}  ❓")
                continue

            slots      = data.get("data", [])
            resultaten = verwerk_slots(slots, datums)

            for datum, (vrije, slots_list) in resultaten.items():
                if vrije > 0:
                    url = f"{BASE_URL}{SLUGS[ticket_naam]}/?date={datum}"
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

    nieuw, meer, verdwenen = bereken_delta(hits, vorige_staat)
    print(f"\n  📊 Delta: {len(nieuw)} nieuw · {len(meer)} meer · {len(verdwenen)} weg")

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
    run()

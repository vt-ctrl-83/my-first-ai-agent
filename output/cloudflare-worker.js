// Colosseum Ticket Checker — Cloudflare Worker
// Requires: KV namespace bound as TICKET_STATE, secret NTFY_TOPIC
// Cron: */10 * * * *

const TARGET_DATES = [
  "2026-06-22", "2026-06-23", "2026-06-24",
  "2026-06-25", "2026-06-26", "2026-06-27", "2026-06-28",
];

const TICKETS = {
  "Underground & Arena":   { id: 225, slug: "full-experience-sotterranei-e-arena" },
  "Full Experience Arena": { id: 76,  slug: "full-experience" },
  "Full Experience Attic": { id: 133, slug: "full-experience-attico" },
  "24h Colosseum":         { id: 35,  slug: "24h-colosseo-foro-romano-palatino" },
};

const API_URL  = "https://ticketing.colosseo.it/mtajax/calendars_month";
const BASE_URL = "https://ticketing.colosseo.it/en/eventi/";

export default {
  // Cron trigger
  async scheduled(event, env, ctx) {
    ctx.waitUntil(checkTickets(env));
  },

  // Manual HTTP trigger — visit the worker URL to test
  async fetch(request, env, ctx) {
    const result = await checkTickets(env);
    return new Response(result, { status: 200, headers: { "content-type": "text/plain" } });
  },
};

async function checkTickets(env) {
  const log = [];

  // Load previous state
  const prevRaw = await env.TICKET_STATE.get("state");
  const prev = prevRaw ? JSON.parse(prevRaw) : {};

  const hits = [];

  for (const [name, ticket] of Object.entries(TICKETS)) {
    const months = groupByMonth(TARGET_DATES);

    for (const [monthStr, dates] of Object.entries(months)) {
      const [year, month] = monthStr.split("-");

      let data;
      try {
        const resp = await fetch(API_URL, {
          method: "POST",
          headers: {
            "accept":           "*/*",
            "content-type":     "application/x-www-form-urlencoded; charset=UTF-8",
            "origin":           "https://ticketing.colosseo.it",
            "referer":          `https://ticketing.colosseo.it/en/eventi/${ticket.slug}/`,
            "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
          },
          body: `action=midaabc_calendars_month&page=${ticket.id}&year=${year}&month=${parseInt(month)}`,
        });

        log.push(`${name} ${monthStr}: HTTP ${resp.status}`);
        if (!resp.ok) continue;
        data = await resp.json();
      } catch (e) {
        log.push(`${name} ${monthStr}: ERROR ${e.message}`);
        continue;
      }

      const slots = data.data || [];

      for (const date of dates) {
        const avail = slots.filter(s => s.startDateTime?.includes(date) && s.capacity > 0);
        const total = avail.reduce((sum, s) => sum + (s.capacity || 0), 0);

        if (total > 0) {
          const times = avail.map(s => {
            const utc = new Date(s.startDateTime);
            const h   = String(utc.getUTCHours() + 2).padStart(2, "0");
            const m   = String(utc.getUTCMinutes()).padStart(2, "0");
            return `${h}:${m}`;
          });
          hits.push({ ticket: name, date, url: `${BASE_URL}${ticket.slug}/?date=${date}`, available: total, times });
          log.push(`  ✅ ${name} ${date} — ${total} plaatsen @ ${times.join(", ")}`);
        } else {
          log.push(`  ❌ ${name} ${date}`);
        }
      }
    }
  }

  // Delta
  const newHits  = hits.filter(h => prev[key(h)] === undefined);
  const moreHits = hits.filter(h => prev[key(h)] !== undefined && h.available > prev[key(h)]);
  const goneKeys = Object.keys(prev).filter(k => !hits.find(h => key(h) === k));

  log.push(`\nDelta: ${newHits.length} new · ${moreHits.length} more · ${goneKeys.length} gone`);

  // Notify
  for (const h of newHits)  await notify(env, `🆕 Nieuw: ${h.ticket}`,   `${h.date} · ${h.available} plaatsen · ${h.times.join(", ")}\n${h.url}`, "urgent", "rotating_light,ticket");
  for (const h of moreHits) await notify(env, `📈 Meer: ${h.ticket}`,    `${h.date} · ${h.available} plaatsen · ${h.times.join(", ")}\n${h.url}`, "high",   "chart_increasing");
  for (const k of goneKeys) {
    const [t, d] = k.split("|");
    await notify(env, `❌ Weg: ${t}`, `${t} op ${d} is niet meer beschikbaar.`, "default", "x");
  }

  // Save state
  const newState = Object.fromEntries(hits.map(h => [key(h), h.available]));
  await env.TICKET_STATE.put("state", JSON.stringify(newState));

  return log.join("\n");
}

async function notify(env, title, message, priority, tags) {
  try {
    await fetch(`https://ntfy.sh/${env.NTFY_TOPIC}`, {
      method: "POST",
      headers: { "Title": title, "Priority": priority, "Tags": tags },
      body: message,
    });
  } catch (e) {
    // notification failure is non-fatal
  }
}

function key(h) { return `${h.ticket}|${h.date}`; }

function groupByMonth(dates) {
  return dates.reduce((acc, d) => {
    const m = d.substring(0, 7);
    (acc[m] = acc[m] || []).push(d);
    return acc;
  }, {});
}

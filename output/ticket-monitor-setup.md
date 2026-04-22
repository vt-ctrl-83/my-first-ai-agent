# Colosseum Ticket Monitor — Setup Guide

## What it does
Checks all 4 ticket types on ticketing.colosseo.it every 10 minutes for June 22–28, 2026.
Sends an email the moment any slot opens.

## Ticket types monitored
- 🏛️  Underground & Arena
- ⚔️  Full Experience Arena
- 🔝 Full Experience Attic
- 🎟️  24h Colosseum

## One-time setup

### 1. Add GitHub Secrets
Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name   | Value                        |
|---------------|------------------------------|
| `GMAIL`       | your Gmail address           |
| `GMAIL_APP_PW`| your Gmail app password      |

To get a Gmail app password:
1. Go to myaccount.google.com → Security → 2-Step Verification (must be enabled)
2. Search "App passwords" → create one for "Mail"
3. Copy the 16-character password (spaces don't matter)

### 2. Enable GitHub Actions
- Go to the **Actions** tab in your repo
- If prompted, click **Enable workflows**

### 3. Test manually
- Go to **Actions → Colosseum Ticket Checker → Run workflow**
- Check the logs — each ticket + date will show ✅ (available) or ❌ (not available)

## Files
- `ticket_checker.py` — Playwright-based checker (intercepts XHR calendar API)
- `.github/workflows/check-tickets.yml` — 10-minute cron schedule
- `requirements.txt` — dependencies (playwright)

## Notes
- Playwright installs Chromium on each run (~1-2 min overhead per run)
- Each full run takes 3–5 minutes due to pacing delays between ticket types
- Public repo = free GitHub Actions minutes, no cost

# Colosseum Ticket Monitor — Setup Guide

## What it does
Checks https://ticketing.colosseo.it every 10 minutes for available slots on June 22–28, 2026.
Sends an urgent push notification to your phone the moment a slot opens.

## One-time setup

### 1. Install ntfy on your phone
- iOS / Android: search **ntfy** in the App Store / Play Store (free, open source)
- Pick a unique topic name — treat it like a password, e.g. `colosseum-rome-abc123`
- In the app: tap **+** → enter your topic name → subscribe

### 2. Add the topic as a GitHub secret
1. Go to your repo on GitHub
2. **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
3. Name: `NTFY_TOPIC`
4. Value: your topic name (e.g. `colosseum-rome-abc123`)
5. Save

### 3. Enable GitHub Actions
- Go to the **Actions** tab in your repo
- If prompted, click **Enable workflows**

### 4. Test it manually
- Go to **Actions** → **Colosseum Ticket Checker** → **Run workflow**
- Check the logs — you should see either "No availability" or "AVAILABLE"

## Files
- `ticket_checker.py` — the checker script
- `.github/workflows/check-tickets.yml` — the schedule
- `requirements.txt` — dependencies

## Troubleshooting
If the script always shows "No availability" even when slots exist:
- The site may render dates via JavaScript (client-side only)
- Download the usage report from a manual run and inspect the raw HTML
- Open an issue and share what date format the site uses — the parser can be updated

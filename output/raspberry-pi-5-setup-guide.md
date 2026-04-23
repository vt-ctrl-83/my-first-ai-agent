# Raspberry Pi 5 — Complete Setup Guide
**Windows laptop · WiFi only · No monitor needed**

---

## What you need to buy

| Item | Notes |
|------|-------|
| Raspberry Pi 5 8GB | The main board |
| Official Pi 5 power supply (27W USB-C) | Don't cheap out here — underpowered PSU causes crashes |
| SD card 64GB+ (Samsung Endurance or SanDisk Endurance) | "Endurance" class lasts longer for 24/7 use |
| Official Pi 5 case with Active Cooler | Has a built-in fan, prevents overheating |
| Micro-HDMI to HDMI cable (optional) | Only if you want to connect a TV/monitor later |

Search **tweakers.net/pricewatch** to compare prices across BE/NL shops.
Best shops: reichelt.de, kiwi-electronics.nl, raspberrypi.com

---

## Part 1 — Prepare the SD card (on your Windows laptop)

### Step 1 — Download Raspberry Pi Imager
1. Go to **raspberrypi.com/software** on your laptop
2. Click "Download for Windows"
3. Install it (standard Next → Next → Finish)

### Step 2 — Flash the SD card
1. Insert the SD card into your laptop (use a USB SD card reader if needed)
2. Open **Raspberry Pi Imager**
3. You'll see three buttons: **Choose Device**, **Choose OS**, **Choose Storage**

**Choose Device:**
- Click it → select **Raspberry Pi 5**

**Choose OS:**
- Click it → select **Raspberry Pi OS (64-bit)** — the first option with the raspberry icon
- This is the full desktop version but we'll use it headless

**Choose Storage:**
- Click it → select your SD card (e.g. "Generic STORAGE DEVICE - 64GB")
- ⚠️ Make sure you pick the SD card, not your laptop drive

4. Click **Next**
5. A popup appears: "Would you like to apply OS customisation settings?" → click **Edit Settings**

### Step 3 — Configure WiFi and SSH (this is the key step)
A settings window opens with tabs: **General** and **Services**

**General tab:**
- ✅ Check "Set hostname" → type: `raspberrypi`
- ✅ Check "Set username and password"
  - Username: `pi`
  - Password: choose something you'll remember (e.g. `colosseum2026`) — write it down
- ✅ Check "Configure wireless LAN"
  - SSID: your WiFi network name (exactly as it appears, capitals matter)
  - Password: your WiFi password
  - Wireless LAN country: **BE** (Belgium)
- ✅ Check "Set locale settings"
  - Timezone: `Europe/Brussels`
  - Keyboard layout: `be` or `us`

**Services tab:**
- ✅ Enable SSH → select "Use password authentication"

6. Click **Save**
7. Back on the main screen, click **Yes** to apply settings
8. Click **Yes** on "Are you sure?" — this will erase the SD card and write the OS
9. Wait ~5 minutes while it writes and verifies
10. When done: "Write Successful" → click **Continue** → remove the SD card

---

## Part 2 — First boot

### Step 4 — Assemble the Pi
1. Slide the SD card into the Pi (small slot on the underside, gold contacts facing the board)
   - It clicks in gently — don't force it
2. Attach the active cooler/fan to the top of the board (it clips onto the GPIO header and two mounting holes)
3. Place it in the case
4. Connect the USB-C power supply

### Step 5 — Wait for it to boot
- The Pi takes **2-3 minutes** on first boot (it expands the filesystem automatically)
- The green LED on the board will blink during boot, then stay mostly on when ready
- During this time it connects to your WiFi automatically using the credentials you configured

### Step 6 — Find the Pi's IP address
You need to find what IP address your router gave the Pi.

**Option A — Router admin page (easiest):**
1. Open your browser and go to your router's admin page
   - Proximus router: `192.168.1.1`
   - Telenet router: `192.168.0.1` or `192.168.1.1`
2. Log in (credentials are usually on a sticker on the router)
3. Look for "Connected devices" or "DHCP clients"
4. Find "raspberrypi" in the list → note its IP (e.g. `192.168.1.42`)

**Option B — Network scanner:**
1. Download **Advanced IP Scanner** (free, Windows)
2. Click Scan — it lists all devices on your network
3. Find "raspberrypi" in the list → note its IP

### Step 7 — Connect via SSH
SSH is how you type commands to the Pi from your laptop — like a remote keyboard.

1. Press **Windows key + R** → type `cmd` → Enter (opens Command Prompt)
2. Type: `ssh pi@192.168.1.42` (replace with your Pi's actual IP)
3. First time: it says "The authenticity of host can't be established... continue?" → type `yes` → Enter
4. Password prompt → type your password (e.g. `colosseum2026`) → Enter
   - Note: you won't see the password as you type — that's normal
5. You should now see: `pi@raspberrypi:~ $`

**You're in. You're now controlling the Pi from your laptop.**

---

## Part 3 — Initial setup

### Step 8 — Update everything
Copy and paste these commands one by one. Wait for each to finish before the next.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git
```

This takes ~5-10 minutes on first run.

### Step 9 — Set a static IP (so it never changes)
Ask your router to always give the Pi the same IP address:
1. Go back to your router admin page
2. Find the Pi in the connected devices list
3. Look for "Reserve IP" or "Static DHCP" → reserve the current IP for the Pi's MAC address
4. Save

This means you can always SSH to the same IP address in the future.

---

## Part 4 — Install the Ticket Checker

### Step 10 — Create the project folder
```bash
mkdir ~/ticket-checker
cd ~/ticket-checker
```

### Step 11 — Create the script
```bash
nano ticket_checker.py
```
This opens a text editor in the terminal. Paste the full contents of your `ticket_checker.py` file.
- To paste in terminal: **right-click** (not Ctrl+V)
- When done: **Ctrl+X** → **Y** → **Enter** to save

### Step 12 — Install dependencies
```bash
pip3 install requests
```

### Step 13 — Test it manually
```bash
NTFY_TOPIC=your-ntfy-topic-here python3 ticket_checker.py
```
Replace `your-ntfy-topic-here` with your actual ntfy topic name.
You should see the results printed. Check your phone for a notification.

### Step 14 — Create a config file for the secret
```bash
nano ~/.ticket_env
```
Add this line:
```
export NTFY_TOPIC=your-ntfy-topic-here
```
Save: **Ctrl+X** → **Y** → **Enter**

Secure it:
```bash
chmod 600 ~/.ticket_env
```

### Step 15 — Schedule it with cron (runs every 10 minutes, forever)
```bash
crontab -e
```
First time: it asks which editor → type `1` (nano) → Enter

Add this line at the bottom:
```
*/10 * * * * source ~/.ticket_env && cd ~/ticket-checker && python3 ticket_checker.py >> ~/ticket-checker/checker.log 2>&1
```
Save: **Ctrl+X** → **Y** → **Enter**

The ticket checker now runs every 10 minutes automatically, even after reboots.

**Check the log to confirm it's running:**
```bash
cat ~/ticket-checker/checker.log
```

---

## Part 5 — Pi-hole (Ad Blocker for your whole network)

**What it does:** Blocks ads, trackers, and adult content on every device in your house — phone, TV, tablet, laptop — without installing anything on those devices. Works by acting as your network's DNS server and blocking requests to known bad domains.

### Step 16 — Install Pi-hole
```bash
curl -sSL https://install.pi-hole.net | bash
```
A blue/purple installation wizard appears. Go through it:
- **Upstream DNS provider** → select **Cloudflare** (1.1.1.1) — fast and private
- **Block lists** → leave defaults checked (StevenBlack list)
- **Install web admin interface** → Yes
- **Install lighttpd** → Yes
- **Enable logging** → Yes
- At the end it shows you: the **web interface URL** and an **admin password** — **write these down**

### Step 17 — Point your router's DNS to the Pi
This makes every device on your network use Pi-hole automatically.

1. Go to your router admin page
2. Find **DNS settings** (usually under LAN or DHCP settings)
3. Set **Primary DNS** to your Pi's IP address (e.g. `192.168.1.42`)
4. Set **Secondary DNS** to `1.1.1.1` (fallback if Pi is down)
5. Save and reboot the router

### Step 18 — Access Pi-hole dashboard
Open your browser and go to: `http://192.168.1.42/admin`
Log in with the password from Step 16.

You'll see a dashboard showing how many requests are being blocked in real time.

### Step 19 — Add adult content blocklist
1. In Pi-hole dashboard → **Adlists** → **Add a new adlist**
2. Add these URLs one by one:
   - `https://raw.githubusercontent.com/nicholasstephan/blocked-domains/main/domains.txt`
   - `https://blocklistproject.github.io/Lists/adult.txt`
   - `https://blocklistproject.github.io/Lists/gambling.txt`
3. Go to **Tools** → **Update Gravity** → click **Update** (applies the new lists)

Now adult and gambling sites are blocked network-wide.

---

## Part 6 — VPN (Access your home network from anywhere)

**What it does:** When you're on public WiFi (café, hotel, airport), your traffic goes through your home internet connection — encrypted and private. Also lets you access your home devices remotely.

### Step 20 — Install PiVPN
```bash
curl -L https://install.pivpn.io | bash
```
Installation wizard:
- **VPN protocol** → select **WireGuard** (faster and more modern than OpenVPN)
- **Port** → leave default (51820)
- **DNS provider** → select **Pi-hole** (your ads stay blocked even on VPN)
- **Public IP** → select the dynamic DNS option if your home IP changes

### Step 21 — Create a VPN profile for your phone
```bash
pivpn add
```
Give it a name (e.g. `vincent-phone`)

Show the QR code:
```bash
pivpn -qr vincent-phone
```

On your phone:
1. Install **WireGuard** app (free, iOS/Android)
2. Tap **+** → **Scan QR code**
3. Scan the QR code from the terminal
4. Toggle it on → you're connected through your home network

---

## Part 7 — Nextcloud (Your own Google Drive + Google Photos)

**What it does:** Store all your files and photos on your own hardware. No monthly fee, no storage limit (except your SD card/external drive), no Google having your data.

### Step 22 — Install Nextcloud via Snap
```bash
sudo snap install nextcloud
```

### Step 23 — Create admin account
```bash
sudo nextcloud.manual-install admin YourAdminPassword
```

### Step 24 — Access Nextcloud
Open browser on any device on your home network:
`http://192.168.1.42`

Log in with the admin credentials you just set.

Install the **Nextcloud** app on your phone → add your Pi's IP as the server → your photos automatically sync.

---

## Part 8 — Home Assistant (Smart Home Hub)

**What it does:** Control all your smart devices from one place — lights, heating, cameras, door sensors, plugs — without any cloud subscription. Works with Philips Hue, IKEA Tradfri, Sonos, Nest, Ring, and hundreds more.

### Step 25 — Install Home Assistant
```bash
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker

mkdir ~/homeassistant
cd ~/homeassistant

cat > docker-compose.yml << 'EOF'
version: '3'
services:
  homeassistant:
    image: homeassistant/home-assistant:stable
    container_name: homeassistant
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./config:/config
EOF

sudo docker-compose up -d
```

### Step 26 — Access Home Assistant
Open browser: `http://192.168.1.42:8123`

First boot takes ~2 minutes. Then follow the setup wizard to add your devices.

---

## Part 9 — Immich (Your own Google Photos with AI)

**What it does:** Automatically backs up photos from your phone. Recognizes faces, objects, places. Exactly like Google Photos but running on your own Pi — free forever, unlimited storage.

### Step 27 — Install Immich
```bash
mkdir ~/immich
cd ~/immich
wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
wget -O .env https://github.com/immich-app/immich/releases/latest/download/example.env
sudo docker-compose up -d
```

Access at: `http://192.168.1.42:2283`

Install **Immich** app on your phone → add your server → enable auto-backup.

---

## Part 10 — Vaultwarden (Your own Password Manager)

**What it does:** Self-hosted Bitwarden — a full-featured password manager. Replaces 1Password (~€3/month) or LastPass. Works on all devices via browser extension and mobile app.

### Step 28 — Install Vaultwarden
```bash
sudo docker run -d \
  --name vaultwarden \
  -v ~/vaultwarden:/data \
  -p 8080:80 \
  --restart unless-stopped \
  vaultwarden/server:latest
```

Access at: `http://192.168.1.42:8080`

Create your account → install the **Bitwarden** browser extension on your laptop → change the server URL to your Pi's address → log in.

---

## Useful commands to remember

```bash
# SSH into the Pi from your laptop
ssh pi@192.168.1.42

# Check ticket checker log
cat ~/ticket-checker/checker.log

# See running cron jobs
crontab -l

# Reboot the Pi
sudo reboot

# Check Pi temperature (should stay under 70°C)
vcgencmd measure_temp

# Check disk space
df -h

# Update everything
sudo apt update && sudo apt upgrade -y
```

---

## Recommended order of setup

1. ✅ Flash SD card + first boot (Part 1-3) — 30 min
2. ✅ Ticket checker (Part 4) — 15 min
3. ✅ Pi-hole + content filter (Part 5) — 20 min
4. ✅ PiVPN (Part 6) — 15 min
5. ✅ Vaultwarden (Part 10) — 10 min
6. ⏳ Nextcloud (Part 7) — 20 min — do this when you want to move off Google Drive
7. ⏳ Immich (Part 9) — 20 min — do this when you want to move off Google Photos
8. ⏳ Home Assistant (Part 8) — 1 hour+ — do this when you have smart home devices

---

*Guide written for Raspberry Pi 5 8GB · Raspberry Pi OS 64-bit · Windows setup*

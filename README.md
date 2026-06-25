# 📡 Job Radar — Raj Sakhiya

Daily top-10 job matches delivered to Telegram. Scored with ATS-style matching against your profile.

## What it does

- Runs every day at **7:00 AM CET**
- Scrapes: **Arbeitnow**, **Greenhouse** (Celonis, Personio, etc.), **Jobicy**, **Adzuna** (StepStone/Indeed aggregator)
- Scores each job 0–100 against your profile (skills, title, location, salary, language)
- Sends top 10 to **Telegram** with: Apply link, ATS keywords to add to your resume, score breakdown
- Password-protected **web dashboard** at `your-render-url/digest`
- Interactive Telegram buttons: Apply / Save / Skip / Rerun with custom hours / Global search

## Deploy to Render (5 min)

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Job Radar v1"
git remote add origin https://github.com/YOUR_USERNAME/job-radar.git
git push -u origin main
```

### 2. Connect to Render
1. Go to **https://render.com** → Sign in with GitHub
2. Click **New → Blueprint**
3. Connect your `job-radar` repo
4. Render auto-detects `render.yaml` — click **Apply**
5. Fill in the **Environment Variables** (see below) → **Save**

### Environment Variables on Render
| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `DASHBOARD_PASSWORD` | Password for the web dashboard |
| `ADZUNA_APP_ID` | From https://developer.adzuna.com |
| `ADZUNA_APP_KEY` | From https://developer.adzuna.com |
| `FLASK_SECRET` | Leave empty — Render auto-generates |

### 3. Done
- Render builds and deploys automatically
- Your bot will ping you at **7:00 AM CET** every day
- Dashboard: `https://job-radar.onrender.com/digest`
- Use `/today`, `/rerun 48`, `/global` anytime on Telegram

## Dashboard

```
URL:     https://job-radar.onrender.com/digest
User:    raj
Pass:    (your DASHBOARD_PASSWORD)
```

## Adzuna Quota

Free tier: **250 calls/month**
- We use **~8 calls/day** (rotating search queries)
- Monthly usage: ~240 calls — well within limit
- Quota resets on the 1st of each month

To register for Adzuna: https://developer.adzuna.com/signup (free, no card)

## Your Profile

- **Name:** Raj Sakhiya
- **Target roles:** RPA Developer, Automation Engineer, Test Automation, AI Workflow, Product Owner
- **Location:** Regensburg (onsite) · ≤200km (hybrid) · rest of DE (remote)
- **Min salary:** €60,000/year
- **Languages:** English (fluent), German (B1)
- **Visa:** No sponsorship needed
- **Availability:** Immediate

## Manual Commands (Telegram)

| Command | What it does |
|---|---|
| `/today` | Show today's top 10 |
| `/rerun 48` | Rerun with last 48 hours window |
| `/global` | Search worldwide (not just Germany) |
| `/start` | Welcome + help |
| `/help` | Command list |

## Project Structure

```
job-radar/
├── src/
│   ├── config.py          # Profile + all knobs
│   ├── matcher.py         # ATS scoring engine
│   ├── pipeline.py        # Fetch → filter → score → rank
│   ├── telegram_bot.py   # Bot + interactive buttons
│   ├── dashboard.py       # Flask web UI
│   ├── scheduler.py       # 7am cron + bot polling
│   └── sources/
│       ├── arbeitnow.py   # 500 jobs, paginated
│       ├── greenhouse.py  # 280+ DE tech jobs
│       ├── jobicy.py     # Remote EU jobs
│       ├── adzuna.py    # StepStone/Indeed aggregator
│       ├── lever.py      # justwatch, aleph
│       ├── stepstone.py  # Captcha-blocked (needs proxy)
│       └── indeed_de.py  # Captcha-blocked (needs proxy)
├── data/
│   ├── seen_jobs.json    # Dedupe across days
│   ├── saved_jobs.json   # Your saved jobs
│   └── adzuna_quota.json # Monthly quota tracker
├── requirements.txt
├── start.sh
└── render.yaml
```

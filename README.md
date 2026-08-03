# 🎯 Pro Cert Radar v4.0 — Ultimate Voucher Hunter

Automatically monitors **45+ high-signal sources** across Reddit, Google News, Twitter, Microsoft Official pages, and more — emails you when **real** Microsoft certification vouchers, training events, or discount deals are posted.

> **v4.0 is built to never miss a deal.** Relaxed scoring, massively expanded sources, and a daily digest so you always know it's working.

## 🚀 What's New in v4.0

| Feature | v3.0 | v4.0 |
|---------|------|------|
| Sources | 21 RSS feeds | **45+ channels** (RSS, JSON API, web scraping, Nitter) |
| Reddit | RSS only (often blocked) | **RSS + JSON API search** (bypasses rate limits) |
| Twitter | None | **Nitter RSS** (best-effort, 3 instance fallback) |
| Scoring threshold | ≥ 3 points | **≥ 2 points** (catches more borderline deals) |
| CRITICAL in summary | +3 pts (weak) | **+8 pts** (summary mentions are strong signals) |
| Actionability gate | Required for CRITICAL | **Removed for CRITICAL** (free voucher = always valuable) |
| Tech word gate | Always required | **Bypassed for strong CRITICAL** (score ≥ 8) |
| Exclude keywords | 30+ terms (too aggressive) | **Trimmed to ~20** (only truly irrelevant) |
| Regex matching | None | **8 regex patterns** for natural language |
| URL detection | None | **14 URL patterns** auto-boost known deal domains |
| Daily digest | None | **Heartbeat email** with stats, near-misses, source health |
| Debug logging | None | **Full debug_log.json** — every post scored and tracked |
| CLI flags | `--test-email` | `--test-email`, `--dry-run`, `--debug`, `--digest` |
| Cron schedule | Every 30 min | **Every 15 min** |
| Keyword coverage | ~60 keywords | **200+ keywords** across all tiers |

## 🧠 How the v4.0 Scoring Engine Works

Every post goes through **4 relaxed gates** before becoming an alert:

```
Post → Gate 1: EXCLUDE filter (trimmed — only obvious spam)
     → Gate 2: Score calculation (CRITICAL, EVENT, DISCOUNT, INFO, regex, URL boost)
     → Gate 3: Tech word check (BYPASSED for score ≥ 8)
     → Gate 4: Score threshold (≥ 2 pts — lowered from 3)
     → ✅ Alert
```

| Signal | Points | Description |
|--------|--------|-------------|
| CRITICAL keyword in **title** | +10 | Definitive voucher post |
| CRITICAL keyword in **summary** | +8 | Strong signal (v4.0: bumped from +3) |
| EVENT keyword + cert context | +6 | Challenge/training event |
| EVENT keyword (no context) | +3 | Possible event mention |
| DISCOUNT keyword + cert context | +4 | Exam discount offer |
| DISCOUNT keyword (no context) | +2 | Possible discount |
| INFO keyword | +2 | General cert news |
| URL from known deal domain | +3 | aka.ms, learn.microsoft.com, etc. |
| Regex: "free...exam/voucher" | +5 | Natural language pattern |
| Regex: "100% off/discount" | +5 | Natural language pattern |
| Regex: "giveaway...voucher" | +4 | Natural language pattern |
| Regex: "50% off" | +3 | Natural language pattern |
| **Minimum threshold** | **≥ 2** | Below = ignored (v3.0 was ≥ 3) |

## 📡 Sources Monitored (45+)

### Reddit RSS (16 subreddits)
**Microsoft-focused:** r/MicrosoftCertifications, r/AzureCertification, r/Azure, r/PowerPlatform, r/PowerApps, r/PowerBI, r/MicrosoftFlow, r/dynamics365

**Broader communities (v4.0):** r/microsoft, r/freebies, r/ITCareerQuestions, r/sysadmin, r/cloudcomputing, r/learnprogramming, r/certs, r/InformationTechnology

### Reddit JSON API Search (8 queries)
Searches ALL of Reddit for voucher posts — bypasses RSS rate limits:
- "free microsoft certification voucher", "free azure exam voucher"
- "cloud skills challenge voucher", "microsoft virtual training day free"
- "microsoft ignite free exam", "microsoft build free certification"
- "free certification exam voucher", "certification voucher giveaway"

### Google News (15 real-time queries)
- Free Microsoft Certification Voucher, Azure Exam Discount
- Cloud Skills Challenge, Dynamics 365 Voucher, Power Apps Voucher
- MS Ignite/Build Voucher & Challenge queries
- **v4.0:** Virtual Training Day, Azure Free Cert 2026, MS Learn Challenge, Applied Skills, Free Cloud Cert

### Microsoft Official (3 feeds)
- Microsoft Learn Blog (TechCommunity)
- Educator Developer Blog (TechCommunity)
- Azure Blog

### YouTube
- Microsoft Learn channel

### Hacker News (3 filtered queries)
- Microsoft Voucher, Azure Certification, Free Certification

### Dev.to (3 tag feeds)
- microsoft, azure, certification

### Twitter/Nitter (best-effort)
- 5 search queries + 3 key accounts (@MSLearn, @AzureSupport, @Microsoft)
- 3 Nitter instances for redundancy

### Web Scraping (10 pages)
- Microsoft Ignite Hub, Microsoft Build Hub
- 30 Days to Learn It (Developer & Credentials pages)
- Microsoft Learn Challenges, Training Events
- **v4.0:** Virtual Training Days, Applied Skills, Reactor Events, Exam Policies

## ⚙️ Setup

### 1. GitHub Secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions**, and add:

| Secret | Value |
|--------|-------|
| `EMAIL_ADDRESS` | Your Gmail address |
| `EMAIL_PASSWORD` | Your [Gmail App Password](https://myaccount.google.com/apppasswords) |
| `TO_EMAIL_ADDRESS` | Primary email for alerts |
| `TO_EMAIL_ADDRESS_2` | *(Optional)* Secondary email for alerts |

### 2. Test
- Go to **Actions** tab → **Pro Cert Radar v4.0** → **Run workflow**
- Or run locally: `python checker.py --test-email`

### 3. CLI Flags
```bash
python checker.py                # Full scan + email alerts
python checker.py --test-email   # Send test email to verify setup
python checker.py --dry-run      # Scan but don't send emails
python checker.py --debug        # Show full scoring breakdown for every post
python checker.py --digest       # Force send daily digest email
```

## 🎨 Alert Priority Levels

| Priority | Emoji | Meaning | Requires |
|----------|-------|---------|----------|
| 🔴 CRITICAL | 🚨 | Free voucher/coupon — act NOW | Score ≥ 8 |
| 🟠 HIGH | 📅 | Event that grants voucher | Score ≥ 6 |
| 🟡 MEDIUM | 💰 | Discounts and deals | Score ≥ 4 |
| 🟢 LOW | 📢 | General cert news | Score ≥ 2 |

## 📧 Email Features
- Beautiful dark-themed HTML emails with alerts grouped by priority
- **Confidence score** shown for each alert (transparency)
- **Daily digest heartbeat** — sent once per day even when no alerts found
  - Shows: posts evaluated, filtered, source health, near-misses
  - You'll always know the system is alive and working
- **Permanent footer** with guaranteed active voucher programs:
  - 🔥 Microsoft Ignite & Build Challenges (free vouchers)
  - 🎁 30 Days to Learn It (50% off vouchers)
  - 🏢 ESI Work Email (50-100% off)
  - 🎓 Student Verification (free fundamentals)
  - 🏅 Microsoft Applied Skills (100% free credentials)
  - 📅 Virtual Training Days (free instructor-led + free voucher)

## 📊 Debug & Monitoring

v4.0 saves these state files (auto-committed to repo):

| File | Purpose |
|------|---------|
| `seen_links.json` | Tracks processed links to avoid duplicates |
| `alert_log.json` | History of all alerts sent (last 500) |
| `debug_log.json` | Every post evaluated with score breakdown (last 1000) |
| `scan_stats.json` | Last digest stats, source health, near-misses |

## 🛡️ False Positive Prevention

v4.0 automatically **excludes** these types of posts:
- ❌ Pure exam result brags ("i passed", "just failed")
- ❌ Physical freebies ("paperback", "t-shirt", "free shipping")
- ❌ Job posts ("salary", "hiring manager", "interview questions")
- ❌ Non-Microsoft vendors (AWS, CompTIA, Cisco posts filtered out)

**Removed from v3.0 exclusions** (these were killing legit posts):
- ~~"should i take"~~ ~~"is it worth"~~ ~~"how hard is"~~ ~~"study tips"~~ ~~"career transition"~~

## 🔧 Technologies Covered

### Microsoft Exam Series Tracked
| Series | Domain | Examples |
|--------|--------|---------|
| **AZ-xxx** | Azure | AZ-900, AZ-104, AZ-204, AZ-305, AZ-400, AZ-500 |
| **DP-xxx** | Data Platform | DP-900, DP-100, DP-203, DP-300, DP-600 |
| **AI-xxx** | AI & Machine Learning | AI-900, AI-102, AI-500 |
| **SC-xxx** | Security | SC-900, SC-100, SC-200, SC-300, SC-400 |
| **PL-xxx** | Power Platform | PL-900, PL-100, PL-200, PL-300, PL-400, PL-600 |
| **MB-xxx** | Dynamics 365 | MB-910, MB-920, MB-210, MB-300, MB-800 |
| **MS-xxx** | Microsoft 365 | MS-900, MS-102, MS-700 |
| **MD-xxx** | Modern Desktop | MD-102 |

# 🎯 Pro Cert Radar v2.0

Automatically monitors **20+ sources** and emails you when free Microsoft certification vouchers, training events, or deals are posted.

## 🚀 What's New in v2.0

| Feature | v1.0 | v2.0 |
|---------|------|------|
| Sources | 5 RSS feeds | 20+ RSS + web scraping |
| Email format | Plain text | Rich HTML with priorities |
| Seen links | Text file | JSON with metadata & auto-cleanup |
| Priority system | 2 tiers | 4 tiers (Critical/High/Medium/Low) |
| Keywords | 13 keywords | 50+ keywords |
| Error handling | Basic | Retry logic + rate limiting |
| Alert history | None | Persistent JSON log |
| Web scraping | None | Microsoft Events, Challenges |
| YouTube monitoring | None | 4 channels |
| Hacker News | None | Filtered search |

## 📡 Sources Monitored

### Reddit (10 subreddits)
- r/MicrosoftCertifications, r/AzureCertification, r/PowerPlatform
- r/dynamics365, r/ITCareerQuestions, r/sysadmin
- r/freebies, r/eFreebies, r/AWSCertifications, r/CompTIA

### Microsoft Official (4 feeds)
- TechCommunity, Learn Blog, Azure Blog, Dev Blogs

### YouTube (4 channels)
- Microsoft Learn, John Savill, TechWorld with Nana, freeCodeCamp

### Other (2+ feeds)
- Hacker News (filtered), Google Alerts (optional)

### Web Scraping (3 pages)
- Microsoft Events, Learn Training Events, Learn Challenges

## ⚙️ Setup

### 1. GitHub Secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions**, and add:

| Secret | Value |
|--------|-------|
| `EMAIL_ADDRESS` | Your Gmail address |
| `EMAIL_PASSWORD` | Your [Gmail App Password](https://myaccount.google.com/apppasswords) |
| `TO_EMAIL_ADDRESS` | Email to receive alerts |

### 2. Push the Code
Replace your existing `checker.py` and `.github/workflows/monitor.yml` with the new files.

### 3. Test
- Go to **Actions** tab → **Pro Cert Radar v2.0** → **Run workflow**
- Or run locally: `python checker.py --test-email`

## 🎨 Alert Priority Levels

| Priority | Emoji | Meaning |
|----------|-------|---------|
| 🔴 CRITICAL | 🚨 | Free voucher/exam — act NOW |
| 🟠 HIGH | 📅 | Event that grants voucher on attendance |
| 🟡 MEDIUM | 💰 | Discounts and deals |
| 🟢 LOW | 📢 | General cert news |

## 📧 Email Preview
You'll receive beautiful dark-themed HTML emails with all alerts grouped by priority in a single message.

## 🛠️ Optional: Add Google Alerts
1. Go to [google.com/alerts](https://www.google.com/alerts)
2. Create alert: `"free Microsoft certification" OR "free exam voucher"`
3. Choose **RSS feed** as delivery method
4. Copy the RSS URL and add it to `RSS_FEEDS` in `checker.py`

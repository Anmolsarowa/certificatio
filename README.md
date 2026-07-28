# 🎯 Pro Cert Radar v3.0

Automatically monitors **21 high-signal sources** and emails you when **real** Microsoft certification vouchers, training events, or discount deals are posted — with near-zero false positives.

## 🚀 What's New in v3.0

| Feature | v2.x | v3.0 |
|---------|------|------|
| Classification | Single keyword match | **Score-based engine** (multi-signal) |
| False positive rate | ~80% | **< 5%** (target) |
| CRITICAL matching | Title + summary blob | **Title-only** (eliminates Reddit boilerplate) |
| Actionability | None | **Actionable words gate** for CRITICAL/HIGH |
| Exclusion filter | 12 spam words | **30+ terms** (study tips, exam results, career posts) |
| Tech domain filter | 50+ broad words | **~35 Microsoft-specific** terms only |
| RSS feeds | 28 feeds (many noisy) | **21 feeds** (high-signal only) |
| Google News | 5 queries | **8 queries** (incl. Ignite & Build) |
| Web scraping | 4 pages | **6 pages** (incl. Ignite & Build hubs) |
| Alert scoring | None | Score displayed in email (transparency) |
| Email footer | None | **Permanent guaranteed voucher programs** section |

## 🧠 How the v3.0 Scoring Engine Works

Every post goes through **4 gates** before becoming an alert:

```
Post → Gate 1: EXCLUDE filter → Gate 2: REQUIRED_TECH check
     → Gate 3: Score threshold (≥3 pts) → Gate 4: Actionability check
     → ✅ Alert
```

| Signal | Points | Description |
|--------|--------|-------------|
| CRITICAL keyword in **title** | +10 | Definitive voucher post |
| CRITICAL keyword in summary only | +3 | Weak signal (needs more) |
| EVENT keyword + cert context | +6 | Challenge/training event |
| DISCOUNT keyword + cert context | +4 | Exam discount offer |
| INFO keyword | +2 | General cert news |
| **Minimum threshold** | **≥ 3** | Below = ignored |

## 📡 Sources Monitored

### Reddit (8 Microsoft-focused subreddits)
- r/MicrosoftCertifications, r/AzureCertification, r/Azure
- r/PowerPlatform, r/PowerApps, r/PowerBI, r/MicrosoftFlow (Power Automate)
- r/dynamics365

### Google News (8 real-time voucher queries)
- Free Microsoft Certification Voucher
- Azure Exam Voucher Discount
- Cloud Skills Challenge Voucher
- Dynamics 365 / Power Apps Exam Voucher
- Microsoft Ignite / Build Challenge Voucher

### Microsoft Official
- Microsoft Learn Blog (TechCommunity)

### YouTube
- Microsoft Learn channel

### Hacker News (2 filtered queries)
- Microsoft Voucher, Azure Certification

### Web Scraping (6 pages)
- Microsoft Ignite Hub, Microsoft Build Hub
- 30 Days to Learn It (Developer & Credentials pages)
- Microsoft Learn Challenges, Training Events

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
- Go to **Actions** tab → **Pro Cert Radar v2.0** → **Run workflow**
- Or run locally: `python checker.py --test-email`

## 🎨 Alert Priority Levels

| Priority | Emoji | Meaning | Requires |
|----------|-------|---------|----------|
| 🔴 CRITICAL | 🚨 | Free voucher/coupon — act NOW | Score ≥ 10, actionable title |
| 🟠 HIGH | 📅 | Event that grants voucher | Score ≥ 6, actionable title |
| 🟡 MEDIUM | 💰 | Discounts and deals | Score ≥ 4 |
| 🟢 LOW | 📢 | General cert news | Score ≥ 3 |

## 📧 Email Features
- Beautiful dark-themed HTML emails with alerts grouped by priority
- **Confidence score** shown for each alert (transparency)
- **Permanent footer** with guaranteed active voucher programs:
  - 🔥 Microsoft Ignite & Build Challenges (free vouchers)
  - 🎁 30 Days to Learn It (50% off vouchers)
  - 🏢 ESI Work Email (50-100% off)
  - 🎓 Student Verification (free fundamentals)
  - 🏅 Microsoft Applied Skills (100% free credentials)

## 🛡️ False Positive Prevention

v3.0 automatically **excludes** these types of posts:
- ❌ Study tips & exam prep ("how I passed", "study plan", "tips for")
- ❌ Exam result posts ("passed today", "failed today", "my experience")
- ❌ Career advice ("career transition", "salary", "job market")
- ❌ Physical freebies ("free book", "paperback", "t-shirt")
- ❌ Non-Microsoft vendors (AWS, CompTIA, Cisco posts filtered out)
- ❌ Generic mentions ("feel free to share" in Reddit boilerplate)

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

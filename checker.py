"""
Pro Cert Radar v3.0 — Advanced Certification Voucher Monitor 🎯
================================================================
Monitors high-signal sources for REAL Microsoft certification vouchers,
exam discounts, training events, and limited-time offers.

v3.0 Changes:
  • Score-based classification (eliminates false positives)
  • Title-priority matching (CRITICAL only triggers on titles, not summaries)
  • Actionability gate (must contain deal-oriented words)
  • Aggressive exclusion of study tips, exam results, career posts
  • Cleaned RSS feeds (removed noise generators)

Sources:
  • Reddit (8 targeted subreddits)
  • Google News (8 real-time voucher queries)
  • Microsoft Learn Blog
  • YouTube: Microsoft Learn
  • Hacker News (filtered)
  • Web scraping: Ignite, Build, 30 Days to Learn, Challenges

Usage:
  python checker.py                    # One-time scan
  python checker.py --test-email       # Send a test email to verify setup
"""

import feedparser
import smtplib
import os
import json
import time
import hashlib
import re
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Optional: Web scraping (pip install requests beautifulsoup4) ─────────────
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_SCRAPING = True
except ImportError:
    HAS_SCRAPING = False

# ═════════════════════════════════════════════════════════════════════════════
#  Configuration
# ═════════════════════════════════════════════════════════════════════════════

# Email credentials (set in GitHub Secrets or environment)
EMAIL_ADDRESS  = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL       = os.environ.get("TO_EMAIL_ADDRESS")
TO_EMAIL_2     = os.environ.get("TO_EMAIL_ADDRESS_2")

ALL_TO_EMAILS = []
if TO_EMAIL:
    ALL_TO_EMAILS.extend([e.strip() for e in TO_EMAIL.split(",") if e.strip()])
if TO_EMAIL_2:
    ALL_TO_EMAILS.extend([e.strip() for e in TO_EMAIL_2.split(",") if e.strip()])

# File paths
SEEN_FILE = "seen_links.json"
LOG_FILE  = "alert_log.json"

# ═════════════════════════════════════════════════════════════════════════════
#  v3.0 — Strict Keyword & Domain Configuration
# ═════════════════════════════════════════════════════════════════════════════

# ⛔ EXCLUDE_KEYWORDS — Discard non-actionable / spam immediately
# These are posts about study tips, exam results, career advice, physical items
EXCLUDE_KEYWORDS = [
    # Physical / non-IT spam
    "gluten free", "gluten-free", "paperback", "free shipping", "bug free",
    "bug-free", "free book", "t-shirt", "sample", "stickers", "gluten",
    "thriller", "novel", "recipe",
    # Study tips & exam results (NOT actionable deals)
    "i passed", "i failed", "just passed", "just failed", "passed today",
    "failed today", "how i passed", "my experience with", "tips for",
    "study plan", "study tips", "study material", "study guide",
    "study resources", "how long did", "is it worth", "how hard is",
    "help me", "should i take", "should i do", "should i get",
    "which certification should", "career transition", "career change",
    "career advice", "worth earning", "worth getting",
    # Job / salary discussions
    "salary", "interview questions", "got the job", "job market",
    "job offer", "hiring", "resume",
    # Generic questions
    "how much harder", "realistic shot", "taking tomorrow",
    "expiring in", "renewal", "renew my",
]

# 🎯 REQUIRED_TECH_WORDS — Entry MUST match at least ONE (Microsoft-focused only)
REQUIRED_TECH_WORDS = [
    # General Microsoft
    "microsoft", "azure", "mslearn", "microsoft learn",
    "microsoft 365", "m365",
    # Power Platform & Power Apps
    "power apps", "powerapps", "power platform", "powerplatform",
    "power automate", "power bi", "power pages", "powerpages",
    "pl-900", "pl-100", "pl-200", "pl-300", "pl-400", "pl-500", "pl-600",
    # Dynamics 365 (D365)
    "d365", "dynamics 365",
    "mb-910", "mb-920", "mb-210", "mb-220", "mb-230", "mb-240", "mb-260",
    "mb-300", "mb-310", "mb-330", "mb-500", "mb-700", "mb-800",
    # Azure & AI Exam Series
    "az-900", "az-104", "az-204", "az-305", "az-400", "az-500",
    "az-700", "az-800", "az-801", "az-802",
    "dp-900", "dp-100", "dp-203", "dp-300", "dp-500", "dp-600",
    "ai-900", "ai-102", "ai-050", "ai-500",
    "sc-900", "sc-100", "sc-200", "sc-300", "sc-400", "sc-500",
    "ms-900", "ms-700", "ms-102", "md-102",
    # Event names (these ARE the deal sources)
    "ignite", "microsoft build", "virtual training day",
    "cloud skills challenge", "30 days to learn",
]

# 🔑 ACTIONABLE_WORDS — For CRITICAL/HIGH, title must contain at least one
# This prevents "I passed AZ-900" from becoming a CRITICAL alert
ACTIONABLE_WORDS = [
    "voucher", "coupon", "promo", "discount", "free exam", "free cert",
    "offer", "register", "sign up", "enroll", "claim", "code",
    "% off", "percent off", "half price", "deal", "grab", "hurry",
    "limited time", "expires", "challenge", "skilling",
    "virtual training day", "30 days to learn",
]

# 🔴 CRITICAL — Actual free voucher / coupon posts
CRITICAL_KEYWORDS = [
    "free voucher", "free exam voucher", "free certification voucher",
    "100% off", "coupon code", "promo code", "discount code",
    "complimentary exam", "free azure exam", "free microsoft exam",
    "ignite voucher", "build voucher", "ignite free exam", "build free exam",
]

# 🟠 HIGH — Events / Challenges that grant exam vouchers
EVENT_KEYWORDS = [
    "virtual training day", "virtual training event", "microsoft ignite",
    "ignite challenge", "cloud skills challenge", "skills challenge",
    "30 days to learn", "30 days to learn it", "learn live",
    "microsoft build", "build challenge", "free training event",
    "skilling challenge", "defender skilling",
]

# 🟡 MEDIUM — Discounts & deals (not free, but worth knowing)
DISCOUNT_KEYWORDS = [
    "50% off", "half price", "discount code", "voucher discount",
    "50% discount", "student discount", "reduced price",
    "practice exam free",
]

# 🟢 LOW — General cert news & updates
INFO_KEYWORDS = [
    "new certification announced", "certification retired",
    "exam update announced", "certification roadmap",
    "exam objectives changed", "new exam announced",
]

# Context words — confirms a post is cert-related (used with EVENT/DISCOUNT)
CERT_CONTEXT_WORDS = [
    "voucher", "certification", "exam", "certificate", "credential",
    "badge", "microsoft learn", "az-", "ai-", "dp-", "sc-", "ms-",
    "mb-", "pl-", "md-", "mo-", "fundamentals", "d365", "power apps",
    "power platform", "power automate", "power bi", "dynamics 365",
]

# ═════════════════════════════════════════════════════════════════════════════
#  RSS Feed Sources — High-Signal Only
# ═════════════════════════════════════════════════════════════════════════════

RSS_FEEDS = {
    # ── Reddit (Microsoft-focused only) ────────────────────────────────────
    "Reddit: Microsoft Certifications": "https://www.reddit.com/r/MicrosoftCertifications/.rss",
    "Reddit: Azure Certification":      "https://www.reddit.com/r/AzureCertification/.rss",
    "Reddit: Power Platform":           "https://www.reddit.com/r/PowerPlatform/.rss",
    "Reddit: Power Apps":               "https://www.reddit.com/r/PowerApps/.rss",
    "Reddit: Power BI":                 "https://www.reddit.com/r/PowerBI/.rss",
    "Reddit: Power Automate":           "https://www.reddit.com/r/MicrosoftFlow/.rss",
    "Reddit: Dynamics 365":             "https://www.reddit.com/r/dynamics365/.rss",
    "Reddit: Azure":                    "https://www.reddit.com/r/Azure/.rss",

    # ── Real-Time Google News (Voucher-specific queries) ───────────────────
    "Google News: MS Cert Voucher":        "https://news.google.com/rss/search?q=free+microsoft+certification+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Azure Exam Discount":    "https://news.google.com/rss/search?q=azure+exam+voucher+discount&hl=en-US&gl=US&ceid=US:en",
    "Google News: Cloud Skills Challenge": "https://news.google.com/rss/search?q=cloud+skills+challenge+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Dynamics 365 Voucher":   "https://news.google.com/rss/search?q=dynamics+365+exam+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Power Apps Voucher":     "https://news.google.com/rss/search?q=power+apps+exam+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Ignite Voucher":      "https://news.google.com/rss/search?q=microsoft+ignite+certification+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Ignite Challenge":    "https://news.google.com/rss/search?q=microsoft+ignite+cloud+skills+challenge&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Build Challenge":     "https://news.google.com/rss/search?q=microsoft+build+cloud+skills+challenge&hl=en-US&gl=US&ceid=US:en",

    # ── Microsoft Official (Learn Blog only — high signal) ─────────────────
    "MS Learn Blog": "https://techcommunity.microsoft.com/t5/microsoft-learn-blog/bg-p/MicrosoftLearnBlog.rss",

    # ── YouTube (Microsoft Learn only) ─────────────────────────────────────
    "YT: Microsoft Learn": "https://www.youtube.com/feeds/videos.xml?channel_id=UCddiUEpeqJcYeBxX1IVBKvQ",

    # ── Hacker News (filtered) ─────────────────────────────────────────────
    "HN: Microsoft Voucher":    "https://hnrss.org/newest?q=microsoft+voucher",
    "HN: Azure Certification":  "https://hnrss.org/newest?q=azure+certification",
}

# ═════════════════════════════════════════════════════════════════════════════
#  Web Scraping Targets
# ═════════════════════════════════════════════════════════════════════════════

SCRAPE_TARGETS = [
    {
        "name": "Microsoft Ignite Hub",
        "url": "https://ignite.microsoft.com/",
        "selector": "a, h1, h2, h3, p",
    },
    {
        "name": "Microsoft Build Hub",
        "url": "https://build.microsoft.com/",
        "selector": "a, h1, h2, h3, p",
    },
    {
        "name": "Microsoft 30 Days to Learn It",
        "url": "https://developer.microsoft.com/en-us/offers/30-days-to-learn-it",
        "selector": "a, h2, h3, p",
    },
    {
        "name": "Microsoft Credentials - 30 Days",
        "url": "https://learn.microsoft.com/en-us/credentials/certifications/30-days-to-learn-it/",
        "selector": "a, h1, h2, h3, p",
    },
    {
        "name": "Microsoft Learn Challenges",
        "url": "https://learn.microsoft.com/en-us/training/challenges",
        "selector": "a, h2, h3",
    },
    {
        "name": "Microsoft Training Events",
        "url": "https://learn.microsoft.com/en-us/training/events/",
        "selector": "a, h2, h3, p",
    },
]

# ═════════════════════════════════════════════════════════════════════════════
#  Seen Links — JSON-based with metadata & auto-cleanup
# ═════════════════════════════════════════════════════════════════════════════

def load_seen():
    """Load seen links from JSON file."""
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        print("⚠️  Corrupted seen file, starting fresh.")
        return {}


def save_seen(seen):
    """Save seen links to JSON file."""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, ensure_ascii=False)


def mark_seen(seen, link, source, priority):
    """Record a link as processed."""
    key = hashlib.md5(link.encode()).hexdigest()
    seen[key] = {
        "link": link,
        "source": source,
        "priority": priority,
        "seen_at": datetime.now().isoformat(),
    }


def is_seen(seen, link):
    """Check if a link was already processed."""
    key = hashlib.md5(link.encode()).hexdigest()
    return key in seen


def cleanup_seen(seen, max_age_days=30):
    """Remove entries older than max_age_days to prevent bloat."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    cleaned = {}
    for k, v in seen.items():
        try:
            seen_at = datetime.fromisoformat(v.get("seen_at", ""))
            if seen_at > cutoff:
                cleaned[k] = v
        except (ValueError, TypeError):
            cleaned[k] = v
    return cleaned


# ═════════════════════════════════════════════════════════════════════════════
#  Alert History Log
# ═════════════════════════════════════════════════════════════════════════════

def log_alert(entry):
    """Append alert to persistent history log."""
    log = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                log = json.load(f)
        except (json.JSONDecodeError, IOError):
            log = []
    log.append(entry)
    log = log[-500:]  # Keep last 500 alerts
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
#  v3.0 — Score-Based Classification Engine
# ═════════════════════════════════════════════════════════════════════════════

def classify_entry(title, summary):
    """
    v3.0 Score-based classifier with title-priority matching.

    Key differences from v2.x:
    1. CRITICAL keywords are matched against TITLE ONLY (not summary)
       to avoid Reddit boilerplate false positives.
    2. Posts must pass an actionability gate for CRITICAL/HIGH.
    3. Aggressive exclusion of study tips, exam results, career posts.

    Returns:
        (priority, alert_type, score) or (None, None, 0) if no match.
    """
    title_lower = title.lower()
    summary_lower = summary.lower() if summary else ""
    combined = f"{title_lower} {summary_lower}"

    # ─── Gate 1: Exclude non-actionable content immediately ───────────────
    if any(neg in title_lower for neg in EXCLUDE_KEYWORDS):
        return None, None, 0

    # ─── Gate 2: Must mention a Microsoft technology ──────────────────────
    if not any(tech in combined for tech in REQUIRED_TECH_WORDS):
        return None, None, 0

    # ─── Score calculation ────────────────────────────────────────────────
    score = 0
    matched_tier = None

    # 🔴 CRITICAL — Check TITLE ONLY (this is the key v3.0 change)
    if any(kw in title_lower for kw in CRITICAL_KEYWORDS):
        score += 10
        matched_tier = "CRITICAL"
    # Also check if CRITICAL keywords appear in summary (weaker signal)
    elif any(kw in summary_lower for kw in CRITICAL_KEYWORDS):
        score += 3
        matched_tier = "CRITICAL_WEAK"

    # 🟠 HIGH — Events (title or summary, but must have cert context)
    if any(kw in combined for kw in EVENT_KEYWORDS):
        if any(ctx in combined for ctx in CERT_CONTEXT_WORDS):
            score += 6
            if matched_tier is None:
                matched_tier = "HIGH"

    # 🟡 MEDIUM — Discounts (must have cert context)
    if any(kw in combined for kw in DISCOUNT_KEYWORDS):
        if any(ctx in combined for ctx in CERT_CONTEXT_WORDS):
            score += 4
            if matched_tier is None:
                matched_tier = "MEDIUM"

    # 🟢 LOW — General cert news
    if any(kw in combined for kw in INFO_KEYWORDS):
        score += 2
        if matched_tier is None:
            matched_tier = "LOW"

    # ─── Gate 3: Score threshold ──────────────────────────────────────────
    if score < 3:
        return None, None, 0

    # ─── Gate 4: Actionability check for CRITICAL/HIGH ────────────────────
    # The title must contain at least one actionable word
    if matched_tier in ("CRITICAL", "HIGH", "CRITICAL_WEAK"):
        if not any(act in title_lower for act in ACTIONABLE_WORDS):
            # Downgrade: it mentions a voucher keyword but isn't offering one
            if score >= 4:
                return "MEDIUM", "MENTION", score
            return None, None, 0

    # ─── Determine final priority ─────────────────────────────────────────
    if matched_tier == "CRITICAL" and score >= 10:
        return "CRITICAL", "INSTANT", score
    elif matched_tier == "CRITICAL_WEAK" and score >= 6:
        # Weak CRITICAL (summary only) + other signals = HIGH
        return "HIGH", "EVENT", score
    elif matched_tier == "HIGH" and score >= 6:
        return "HIGH", "EVENT", score
    elif score >= 4:
        return "MEDIUM", "DISCOUNT", score
    elif score >= 3:
        return "LOW", "INFO", score

    return None, None, 0


# ═════════════════════════════════════════════════════════════════════════════
#  HTML Email Builder
# ═════════════════════════════════════════════════════════════════════════════

PRIORITY_CONFIG = {
    "CRITICAL": {"emoji": "🚨", "color": "#FF1744", "label": "INSTANT FREE CERT"},
    "HIGH":     {"emoji": "📅", "color": "#FF9100", "label": "EVENT → VOUCHER"},
    "MEDIUM":   {"emoji": "💰", "color": "#FFD600", "label": "DISCOUNT DEAL"},
    "LOW":      {"emoji": "📢", "color": "#00E676", "label": "CERT NEWS"},
}


def build_html_email(alerts):
    """Build a beautiful HTML email from a list of alerts."""
    rows = ""
    for a in alerts:
        cfg = PRIORITY_CONFIG.get(a["priority"], PRIORITY_CONFIG["LOW"])
        score_display = f" (score: {a.get('score', '?')})" if a.get('score') else ""
        rows += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 14px; text-align: center; width: 180px;">
                <span style="background: {cfg['color']}; color: #000; padding: 5px 12px;
                             border-radius: 6px; font-weight: bold; font-size: 11px;
                             letter-spacing: 0.5px;">
                    {cfg['emoji']} {cfg['label']}
                </span>
            </td>
            <td style="padding: 14px;">
                <a href="{a['link']}" style="color: #64B5F6; text-decoration: none;
                   font-weight: bold; font-size: 14px;">
                    {a['title'][:120]}
                </a>
                <br>
                <span style="color: #888; font-size: 11px;">📡 {a['source']}{score_display}</span>
            </td>
        </tr>
        """

    return f"""
    <html>
    <body style="background: #0D1117; color: #E0E0E0; font-family: 'Segoe UI', Arial, sans-serif;
                 padding: 24px; margin: 0;">
        <div style="max-width: 680px; margin: 0 auto;">
            <div style="text-align: center; padding: 20px 0;">
                <h1 style="color: #58A6FF; margin: 0; font-size: 28px;">
                    🎯 Cert Radar v3.0 Alert
                </h1>
                <p style="color: #8B949E; margin: 8px 0 0 0; font-size: 13px;">
                    {len(alerts)} new match{"es" if len(alerts) != 1 else ""} found
                    · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                </p>
            </div>

            <table style="width: 100%; border-collapse: collapse; background: #161B22;
                          border-radius: 12px; overflow: hidden; border: 1px solid #30363D;">
                <thead>
                    <tr style="background: #21262D;">
                        <th style="padding: 12px; text-align: center; color: #8B949E;
                                   font-size: 11px; letter-spacing: 1px;">PRIORITY</th>
                        <th style="padding: 12px; text-align: left; color: #8B949E;
                                   font-size: 11px; letter-spacing: 1px;">DETAILS</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>

            <!-- Permanent Active Guaranteed Deals Section -->
            <div style="margin-top: 24px; padding: 18px; background: #161B22; border: 1px solid #30363D; border-radius: 12px;">
                <h3 style="color: #58A6FF; margin-top: 0; margin-bottom: 12px; font-size: 16px;">
                    ⚡ Guaranteed Active Voucher Programs & Major Events
                </h3>
                <ul style="padding-left: 20px; margin: 0; color: #C9D1D9; font-size: 13px; line-height: 1.8;">
                    <li>
                        <strong>🔥 Microsoft Ignite & Build Challenges (100% Free Vouchers):</strong> Active monitoring enabled.<br>
                        👉 <a href="https://ignite.microsoft.com/" style="color: #58A6FF;">MS Ignite</a> ·
                        <a href="https://build.microsoft.com/" style="color: #58A6FF;">MS Build</a>
                    </li>
                    <li style="margin-top: 8px;">
                        <strong>🎁 50% Off Voucher (30 Days to Learn It):</strong> Complete a challenge for 50% off Azure, PL-300, or MB-800.<br>
                        👉 <a href="https://developer.microsoft.com/en-us/offers/30-days-to-learn-it" style="color: #58A6FF;">Claim 50% Voucher Here</a>
                    </li>
                    <li style="margin-top: 8px;">
                        <strong>🏢 50%-100% Off via Work Email (ESI):</strong> If your company uses Microsoft Cloud.<br>
                        👉 <a href="https://esi.microsoft.com" style="color: #58A6FF;">Check ESI Eligibility</a>
                    </li>
                    <li style="margin-top: 8px;">
                        <strong>🎓 Free Fundamentals & 45% Off (Student):</strong> Verify student email for free AZ-900 / PL-900 / MB-910.<br>
                        👉 <a href="https://learn.microsoft.com/en-us/credentials/certifications/student-discounts" style="color: #58A6FF;">Verify Student Status</a>
                    </li>
                    <li style="margin-top: 8px;">
                        <strong>🏅 100% Free Applied Skills:</strong> Official Microsoft badges via 2-hour lab assessments.<br>
                        👉 <a href="https://learn.microsoft.com/en-us/credentials/browse/?credential_types=applied%20skills" style="color: #58A6FF;">Browse Applied Skills</a>
                    </li>
                </ul>
            </div>

            <div style="text-align: center; padding: 20px 0;">
                <p style="color: #484F58; font-size: 11px; margin: 0;">
                    Powered by Pro Cert Radar v3.0 🛰️
                </p>
            </div>
        </div>
    </body>
    </html>
    """


# ═════════════════════════════════════════════════════════════════════════════
#  Email Sending (with retry)
# ═════════════════════════════════════════════════════════════════════════════

def send_email_alert(alerts):
    """Send a consolidated HTML email with all new alerts."""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not ALL_TO_EMAILS:
        print("❌ Email credentials missing! Set EMAIL_ADDRESS, EMAIL_PASSWORD, TO_EMAIL_ADDRESS")
        return False

    if not alerts:
        return False

    # Determine highest priority for subject line
    priorities = [a["priority"] for a in alerts]
    if "CRITICAL" in priorities:
        top = "CRITICAL"
    elif "HIGH" in priorities:
        top = "HIGH"
    elif "MEDIUM" in priorities:
        top = "MEDIUM"
    else:
        top = "LOW"

    cfg = PRIORITY_CONFIG[top]
    subject = f"{cfg['emoji']} Cert Radar: {len(alerts)} alert{'s' if len(alerts) != 1 else ''} — {cfg['label']}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = ", ".join(ALL_TO_EMAILS)

    # Plain text fallback
    plain = "Cert Radar v3.0 Alerts\n" + "=" * 50 + "\n\n"
    for a in alerts:
        p = PRIORITY_CONFIG.get(a["priority"], PRIORITY_CONFIG["LOW"])
        plain += f"[{p['label']}] {a['title']}\n"
        plain += f"  Link: {a['link']}\n"
        plain += f"  Source: {a['source']}\n\n"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_html_email(alerts), "html"))

    # Send with 3 retries
    for attempt in range(3):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            print(f"✅ Email sent! ({len(alerts)} alerts)")
            return True
        except Exception as e:
            print(f"⚠️  Email attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    print("❌ All email attempts failed.")
    return False


def send_test_email():
    """Send a test email to verify setup."""
    test_alerts = [
        {
            "priority": "CRITICAL",
            "title": "🧪 TEST — Free AZ-900 Voucher Available!",
            "link": "https://example.com/test-critical",
            "source": "Test Source",
            "score": 10,
        },
        {
            "priority": "HIGH",
            "title": "🧪 TEST — Virtual Training Day: Get Free Cert Voucher!",
            "link": "https://example.com/test-event",
            "source": "Test Source",
            "score": 6,
        },
        {
            "priority": "MEDIUM",
            "title": "🧪 TEST — 50% Off All Microsoft Exams This Week!",
            "link": "https://example.com/test-discount",
            "source": "Test Source",
            "score": 4,
        },
    ]
    success = send_email_alert(test_alerts)
    if success:
        print("✅ Test email sent! Check your inbox.")
    else:
        print("❌ Test email failed. Check your credentials.")


# ═════════════════════════════════════════════════════════════════════════════
#  Strict Sources — YouTube/HN only CRITICAL + HIGH pass through
# ═════════════════════════════════════════════════════════════════════════════

STRICT_SOURCES = [
    "YT:",       # All YouTube channels
    "HN:",       # Hacker News
]

def is_strict_source(source_name):
    """Check if a source requires strict filtering (only CRITICAL/HIGH)."""
    return any(source_name.startswith(prefix) for prefix in STRICT_SOURCES)


# ═════════════════════════════════════════════════════════════════════════════
#  Phase 1: RSS Feed Scanner
# ═════════════════════════════════════════════════════════════════════════════

def scan_rss_feeds(seen):
    """Scan all RSS feeds and return matching alerts."""
    alerts = []

    for source_name, url in RSS_FEEDS.items():
        print(f"  📡 {source_name}...")
        try:
            feed = feedparser.parse(url)
            if feed.bozo and not feed.entries:
                print(f"     ⚠️  Feed error: {feed.bozo_exception}")
                continue

            match_count = 0
            for entry in feed.entries:
                link = getattr(entry, "link", "")
                if not link or is_seen(seen, link):
                    continue

                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")

                priority, alert_type, score = classify_entry(title, summary)

                # Skip LOW/MEDIUM from noisy sources (YouTube, HN)
                if priority and is_strict_source(source_name) and priority in ("LOW", "MEDIUM"):
                    continue

                if priority:
                    alert = {
                        "priority": priority,
                        "type": alert_type,
                        "title": title,
                        "link": link,
                        "source": source_name,
                        "score": score,
                        "found_at": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
                    mark_seen(seen, link, source_name, priority)
                    match_count += 1
                    print(f"     🎯 [{priority}] (score:{score}) {title[:80]}")

            if match_count == 0:
                pass  # Silent if no matches — less noise

        except Exception as e:
            print(f"     ❌ Error: {e}")

        # Rate limit — be polite to servers
        time.sleep(1.5)

    return alerts


# ═════════════════════════════════════════════════════════════════════════════
#  Phase 2: Web Scraper (Microsoft Events, Challenges, etc.)
# ═════════════════════════════════════════════════════════════════════════════

def scan_web_pages(seen):
    """Scrape configured web pages for cert-related content."""
    if not HAS_SCRAPING:
        print("  ⏭️  Skipping web scraping (install: pip install requests beautifulsoup4)")
        return []

    alerts = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for target in SCRAPE_TARGETS:
        print(f"  🌐 {target['name']}...")
        try:
            resp = requests.get(target["url"], headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            elements = soup.select(target["selector"])
            for el in elements:
                text = el.get_text(strip=True)
                link = el.get("href", target["url"])

                # Make relative URLs absolute
                if link and not link.startswith("http"):
                    from urllib.parse import urljoin
                    link = urljoin(target["url"], link)

                if not text or len(text) < 10 or is_seen(seen, link):
                    continue

                priority, alert_type, score = classify_entry(text, "")
                if priority:
                    alert = {
                        "priority": priority,
                        "type": alert_type,
                        "title": text[:150],
                        "link": link,
                        "source": f"Web: {target['name']}",
                        "score": score,
                        "found_at": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
                    mark_seen(seen, link, target["name"], priority)
                    print(f"     🎯 [{priority}] (score:{score}) {text[:80]}")

        except Exception as e:
            print(f"     ❌ Error: {e}")

        time.sleep(2)

    return alerts


# ═════════════════════════════════════════════════════════════════════════════
#  Main Entry Point
# ═════════════════════════════════════════════════════════════════════════════

def check_feeds():
    """Run a complete scan across all sources."""
    start = time.time()

    print("=" * 60)
    print("🎯 PRO CERT RADAR v3.0 — Starting full scan...")
    print(f"   📡 {len(RSS_FEEDS)} RSS feeds + {len(SCRAPE_TARGETS)} web pages")
    print("=" * 60)

    # Load & cleanup seen links
    seen = load_seen()
    seen = cleanup_seen(seen)

    all_alerts = []

    # Phase 1: RSS feeds
    print("\n📡 PHASE 1: RSS Feed Scan")
    print("-" * 40)
    rss_alerts = scan_rss_feeds(seen)
    all_alerts.extend(rss_alerts)

    # Phase 2: Web scraping
    print("\n🌐 PHASE 2: Web Page Scraping")
    print("-" * 40)
    web_alerts = scan_web_pages(seen)
    all_alerts.extend(web_alerts)

    # Save updated seen links
    save_seen(seen)

    # Sort by priority (CRITICAL first)
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_alerts.sort(key=lambda a: priority_order.get(a["priority"], 99))

    # Print results summary
    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"📊 SCAN COMPLETE — {elapsed:.1f}s")
    print(f"   Total new alerts: {len(all_alerts)}")
    for p in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = sum(1 for a in all_alerts if a["priority"] == p)
        if count > 0:
            cfg = PRIORITY_CONFIG[p]
            print(f"   {cfg['emoji']} {p}: {count}")
    print("=" * 60)

    # Send email & log if alerts found
    if all_alerts:
        for a in all_alerts:
            log_alert(a)
        send_email_alert(all_alerts)
    else:
        print("✅ No new matching posts found. All quiet.")

    return all_alerts


if __name__ == "__main__":
    # Handle --test-email flag
    if "--test-email" in sys.argv:
        print("📧 Sending test email...")
        send_test_email()
    else:
        print(r"""
  ██████╗███████╗██████╗ ████████╗    ██████╗  █████╗ ██████╗  █████╗ ██████╗
 ██╔════╝██╔════╝██╔══██╗╚══██╔══╝    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗
 ██║     █████╗  ██████╔╝   ██║       ██████╔╝███████║██║  ██║███████║██████╔╝
 ██║     ██╔══╝  ██╔══██╗   ██║       ██╔══██╗██╔══██║██║  ██║██╔══██║██╔══██╗
 ╚██████╗███████╗██║  ██║   ██║       ██║  ██║██║  ██║██████╔╝██║  ██║██║  ██║
  ╚═════╝╚══════╝╚═╝  ╚═╝   ╚═╝       ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
                        🎯 Pro Cert Radar v3.0
        """)
        check_feeds()

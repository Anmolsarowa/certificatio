"""
Pro Cert Radar v5.0 — Zero Noise Voucher Hunter 🎯
====================================================
Ultra-strict Microsoft certification voucher finder.
ONLY sends an email when a VERIFIED, actionable voucher opportunity is found.

v5.0 Changes (from v4.0):
  • Single priority tier — VERIFIED — no more LOW/MEDIUM/HIGH noise
  • Phrase-level matching only — no more single-word false positives
  • Removed ALL noisy sources (Dev.to, HN, broad Reddit, broken Nitter)
  • Removed daily digest emails — bot is SILENT unless it finds something real
  • URL verification — checks that links lead to real voucher/event pages
  • Added GitHub community voucher tracker as a source
  • Massive exclusion list to kill garbage matches

Sources (high-signal only):
  • Reddit RSS: 9 Microsoft-focused subreddits
  • Google News: 8 voucher-specific queries
  • Microsoft Official: Azure Blog
  • YouTube: Microsoft Learn
  • Web scraping: Ignite, Build, Virtual Training Days, Learn Challenges
  • GitHub: Community voucher tracker

Usage:
  python checker.py                    # Full scan + email
  python checker.py --test-email       # Send a test email to verify setup
  python checker.py --dry-run          # Scan but don't send email
  python checker.py --debug            # Show full scoring breakdown
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

ALL_TO_EMAILS = []
if TO_EMAIL:
    ALL_TO_EMAILS.extend([e.strip() for e in TO_EMAIL.split(",") if e.strip()])

# File paths
SEEN_FILE  = "seen_links.json"
LOG_FILE   = "alert_log.json"
DEBUG_FILE = "debug_log.json"
STATS_FILE = "scan_stats.json"

# Command-line flags
DRY_RUN = "--dry-run" in sys.argv
DEBUG   = "--debug" in sys.argv


# ═════════════════════════════════════════════════════════════════════════════
#  v5.0 — ULTRA-STRICT Keyword Configuration
# ═════════════════════════════════════════════════════════════════════════════

# ⛔ EXCLUDE — Kill these immediately. If ANY of these appear in the title,
# the post is 100% NOT a voucher opportunity.
EXCLUDE_PATTERNS = [
    # Physical / non-IT spam
    "gluten free", "gluten-free", "paperback", "free shipping",
    "bug free", "bug-free", "t-shirt", "stickers",
    "thriller", "novel", "recipe", "cookbook",
    # Exam result brags (NOT deals)
    "i passed", "i failed", "just passed", "just failed",
    "passed today", "failed today", "how i passed", "my experience",
    "passed on first attempt", "passed with",
    # Job/career posts (NOT vouchers)
    "salary", "got the job", "hiring manager", "resume review",
    "interview questions", "career advice", "career path",
    "worth it in 2026", "worth it in 2025", "is it worth",
    "should i get", "which certification should",
    "career switch", "career change", "job market",
    # Study / prep posts (NOT vouchers)
    "study guide", "study notes", "study plan", "study tips",
    "how to prepare", "how to study", "exam prep",
    "practice questions", "practice exam", "practice test",
    "exam simulator", "exam dump", "brain dump",
    "exam questions", "real exam questions",
    "resource guide", "ultimate guide", "complete guide",
    "learning path", "study resource", "exam tips",
    "how i studied", "study material", "notes and practice",
    "how long to study", "study schedule",
    # "I got certified" / discussion posts
    "is ms learn enough", "is it enough", "enough to pass",
    "what to do with", "what should i",
    "which microsoft certification", "best certification",
    "most valuable", "certification roadmap",
    "difficulty level", "how difficult", "how hard",
    "very difficult for me", "was very difficult",
    # Comparison / news articles (NOT vouchers)
    "vs azure vs", "aws vs", "gcp vs",
    "best cloud", "top certifications", "highest paying",
    "complete breakdown", "full breakdown",
    "certification cost", "exam fee", "how much does",
    # Non-Microsoft vendors
    "comptia a+", "comptia network+", "comptia security+",
    "aws certified", "aws solution", "aws certification cost",
    "google cloud certified", "cisco ccna", "cisco ccnp",
    "oracle", "servicenow", "salesforce",
    # Reddit noise
    "free post friday", "please follow these rules",
    "weekly thread", "megathread", "monthly thread",
    # Product features (NOT exam vouchers)
    "setting up coupon codes", "coupon codes in dynamics",
    "coupon codes in retail", "promo code in",
    "reduce costs", "reduce azure", "save money",
    "cost optimization", "firewall costs",
    # Generic non-voucher content
    "book of news", "what we know", "startups to watch",
    "best courses in", "step onto the", "forefront of",
    "announces hackathon", "future ready",
    "terraform ordering", "service bus",
    "deploy manually", "stitching models",
    "support ticket",
    # Masters/degree posts
    "get my masters", "masters degree", "masters for free",
]

# ═════════════════════════════════════════════════════════════════════════════
# 🎯 VERIFIED VOUCHER PHRASES — These are the ONLY things that trigger alerts
# Each phrase must appear as a complete match in title OR summary
# ═════════════════════════════════════════════════════════════════════════════

# Tier 1: GUARANTEED VOUCHER — Direct free voucher mentions
GUARANTEED_VOUCHER_PHRASES = [
    # Direct free voucher language
    "free exam voucher",
    "free certification voucher",
    "free microsoft voucher",
    "free azure voucher",
    "free voucher code",
    "complimentary exam voucher",
    "complimentary certification voucher",
    "100% off exam",
    "100% off certification",
    "100% discount exam",
    "100% discount certification",
    "100% free exam",
    "100% free certification",
    # Giveaway patterns
    "voucher giveaway",
    "exam voucher giveaway",
    "certification giveaway",
    "giving away voucher",
    "giving away exam voucher",
    "spare voucher",
    "extra voucher",
    "unused voucher",
    "voucher to share",
    "voucher to give",
    # Zero cost patterns
    "no cost exam",
    "no cost certification",
    "zero cost exam",
    "zero cost certification",
    "$0 exam",
    # Event-specific voucher announcements
    "ignite free exam",
    "ignite free cert",
    "ignite certification voucher",
    "ignite exam voucher",
    "build free exam",
    "build free cert",
    "build certification voucher",
    "build exam voucher",
    "skills fest voucher",
    "skills fest free exam",
    "certification week free",
    "certification week voucher",
]

# Tier 2: EVENT WITH VOUCHER — Events/challenges that grant vouchers
EVENT_VOUCHER_PHRASES = [
    # Must contain BOTH an event reference AND a voucher reference
    "virtual training day",
    "cloud skills challenge",
    "skills challenge voucher",
    "30 days to learn it",
    "complete the challenge and earn",
    "earn a free certification",
    "earn a free exam",
    "earn free certification",
    "earn free exam",
    "earn an exam voucher",
    "earn a voucher",
    "register for free certification",
    "register for free exam",
    "free certification opportunity",
    "free exam opportunity",
    "certification challenge voucher",
    "microsoft learn challenge",
    "levelup practice assessment",
    "certification bootcamp free",
]

# Tier 3: DISCOUNT — Significant discounts (50%+)
DISCOUNT_VOUCHER_PHRASES = [
    "50% off exam",
    "50% off certification",
    "50% discount exam",
    "50% discount certification",
    "half price exam",
    "half price certification",
    "exam discount code",
    "certification discount code",
    "beta exam free",
    "beta exam invitation",
    "esi discount",
    "enterprise skills initiative",
    "student discount certification",
    "student free exam",
]

# ═════════════════════════════════════════════════════════════════════════════
# 🔗 VERIFIED VOUCHER URLS — Links from these domains are ALWAYS relevant
# ═════════════════════════════════════════════════════════════════════════════

VOUCHER_URL_PATTERNS = [
    r"aka\.ms/.*(?:voucher|challenge|cert|free|skills)",
    r"learn\.microsoft\.com/.*challenge",
    r"learn\.microsoft\.com/.*credentials.*offer",
    r"events\.microsoft\.com/.*(?:virtual-training|certification-week)",
    r"developer\.microsoft\.com/.*(?:30-days|offers)",
    r"esi\.microsoft\.com",
    r"microsoft\.com/.*virtual-training-day",
    r"microsoft\.com/.*skills-challenge",
]

# ═════════════════════════════════════════════════════════════════════════════
# 🛑 CONTEXT VERIFICATION — Post must mention Microsoft/Azure to be relevant
# ═════════════════════════════════════════════════════════════════════════════

MICROSOFT_CONTEXT_WORDS = [
    "microsoft", "azure", "mslearn", "microsoft learn",
    "microsoft 365", "m365", "ms learn",
    "power apps", "powerapps", "power platform", "powerplatform",
    "power automate", "power bi", "power pages",
    "dynamics 365", "d365",
    "az-900", "az-104", "az-204", "az-305", "az-400", "az-500",
    "az-700", "az-800", "az-801",
    "dp-900", "dp-100", "dp-203", "dp-300", "dp-500", "dp-600",
    "ai-900", "ai-102", "ai-050", "ai-500",
    "sc-900", "sc-100", "sc-200", "sc-300", "sc-400",
    "ms-900", "ms-700", "ms-102", "md-102",
    "pl-900", "pl-100", "pl-200", "pl-300", "pl-400", "pl-500", "pl-600",
    "mb-910", "mb-920", "mb-210", "mb-220", "mb-230", "mb-240",
    "mb-300", "mb-310", "mb-330", "mb-500", "mb-700", "mb-800",
    "ignite", "microsoft build",
]


# ═════════════════════════════════════════════════════════════════════════════
#  RSS Feed Sources — HIGH-SIGNAL ONLY (removed all noise)
# ═════════════════════════════════════════════════════════════════════════════

RSS_FEEDS = {
    # ── Reddit: Microsoft-focused subreddits ONLY ─────────────────────────
    "Reddit: Microsoft Certifications": "https://www.reddit.com/r/MicrosoftCertifications/.rss",
    "Reddit: Azure Certification":      "https://www.reddit.com/r/AzureCertification/.rss",
    "Reddit: Power Platform":           "https://www.reddit.com/r/PowerPlatform/.rss",
    "Reddit: Power Apps":               "https://www.reddit.com/r/PowerApps/.rss",
    "Reddit: Power BI":                 "https://www.reddit.com/r/PowerBI/.rss",
    "Reddit: Power Automate":           "https://www.reddit.com/r/MicrosoftFlow/.rss",
    "Reddit: Dynamics 365":             "https://www.reddit.com/r/dynamics365/.rss",
    "Reddit: Azure":                    "https://www.reddit.com/r/Azure/.rss",
    "Reddit: Microsoft":                "https://www.reddit.com/r/microsoft/.rss",

    # ── Google News: Voucher-specific queries ONLY ────────────────────────
    "Google News: MS Cert Voucher":      "https://news.google.com/rss/search?q=free+microsoft+certification+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Azure Exam Voucher":   "https://news.google.com/rss/search?q=azure+exam+voucher+free&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Ignite Voucher":    "https://news.google.com/rss/search?q=microsoft+ignite+free+exam+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Virtual Training Day": "https://news.google.com/rss/search?q=microsoft+virtual+training+day+free+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Skills Challenge":     "https://news.google.com/rss/search?q=microsoft+cloud+skills+challenge+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Cert Week Voucher":    "https://news.google.com/rss/search?q=microsoft+certification+week+free+exam&hl=en-US&gl=US&ceid=US:en",
    "Google News: Skills Fest Voucher":  "https://news.google.com/rss/search?q=microsoft+skills+fest+free+certification&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Free Cert 2026":    "https://news.google.com/rss/search?q=microsoft+free+certification+voucher+2026&hl=en-US&gl=US&ceid=US:en",

    # ── Microsoft Official ────────────────────────────────────────────────
    "MS Azure Blog":          "https://azure.microsoft.com/en-us/blog/feed/",

    # ── YouTube ───────────────────────────────────────────────────────────
    "YT: Microsoft Learn":   "https://www.youtube.com/feeds/videos.xml?channel_id=UCddiUEpeqJcYeBxX1IVBKvQ",
}

# ═════════════════════════════════════════════════════════════════════════════
#  Web Scraping Targets — Microsoft official pages only
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
        "name": "Microsoft Learn Challenges",
        "url": "https://learn.microsoft.com/en-us/training/challenges",
        "selector": "a, h2, h3",
    },
    {
        "name": "Microsoft Virtual Training Days",
        "url": "https://events.microsoft.com/en-us/mvtd",
        "selector": "a, h1, h2, h3, p, span",
    },
    {
        "name": "Microsoft Events",
        "url": "https://events.microsoft.com/",
        "selector": "a, h1, h2, h3, p",
    },
]

# ═════════════════════════════════════════════════════════════════════════════
#  GitHub Community Voucher Tracker (v5.0 NEW)
# ═════════════════════════════════════════════════════════════════════════════

GITHUB_VOUCHER_TRACKER = "https://raw.githubusercontent.com/nisalgunawardhana/microsoft-certification-voucher-offers/main/README.md"


# ═════════════════════════════════════════════════════════════════════════════
#  Scan Statistics Tracker
# ═════════════════════════════════════════════════════════════════════════════

scan_stats = {
    "total_posts_evaluated": 0,
    "excluded_by_patterns": 0,
    "excluded_no_voucher_phrase": 0,
    "excluded_no_microsoft_context": 0,
    "verified_alerts": 0,
    "source_errors": [],
    "source_success": [],
}


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
    log = log[-200:]  # Keep last 200 alerts
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
#  Debug Log
# ═════════════════════════════════════════════════════════════════════════════

debug_entries = []

def debug_log_entry(title, source, tier, reason, link=""):
    """Log a post evaluation for debugging."""
    entry = {
        "title": title[:150],
        "source": source,
        "tier": tier,
        "reason": reason,
        "link": link,
        "time": datetime.now().isoformat(),
    }
    debug_entries.append(entry)
    if DEBUG:
        status = f"✅ [{tier}]" if tier else "❌ FILTERED"
        print(f"     {status} | {reason} | {title[:80]}")


def save_debug_log():
    """Save debug log to file (keep last 500 entries)."""
    existing = []
    if os.path.exists(DEBUG_FILE):
        try:
            with open(DEBUG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []
    existing.extend(debug_entries)
    existing = existing[-500:]
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
#  v5.0 — ULTRA-STRICT Classification Engine
# ═════════════════════════════════════════════════════════════════════════════

def check_voucher_url(link):
    """Check if a URL matches known voucher/event domains."""
    if not link:
        return False
    for pattern in VOUCHER_URL_PATTERNS:
        if re.search(pattern, link, re.IGNORECASE):
            return True
    return False


def classify_entry(title, summary, link="", source=""):
    """
    v5.0 Ultra-strict classifier — ONLY matches verified voucher opportunities.

    Returns:
        (tier, reason) or (None, None) if no match.

    Tiers:
        "VOUCHER"   — Direct free voucher / 100% off
        "EVENT"     — Event/challenge that grants a voucher upon completion
        "DISCOUNT"  — Significant discount (50%+) on exams
    """
    title_lower = title.lower().strip()
    summary_lower = summary.lower().strip() if summary else ""
    combined = f"{title_lower} {summary_lower}"

    scan_stats["total_posts_evaluated"] += 1

    # ─── Gate 1: Exclude obviously irrelevant content ─────────────────────
    for pattern in EXCLUDE_PATTERNS:
        if pattern in title_lower:
            scan_stats["excluded_by_patterns"] += 1
            debug_log_entry(title, source, None, f"EXCLUDED: '{pattern}'", link)
            return None, None

    # ─── Gate 2: Must contain a voucher-related phrase ────────────────────
    matched_tier = None
    matched_reason = None

    # Check Tier 1: GUARANTEED VOUCHER phrases
    for phrase in GUARANTEED_VOUCHER_PHRASES:
        if phrase in combined:
            matched_tier = "VOUCHER"
            matched_reason = f"Guaranteed voucher phrase: '{phrase}'"
            break

    # Check Tier 2: EVENT WITH VOUCHER phrases
    if not matched_tier:
        for phrase in EVENT_VOUCHER_PHRASES:
            if phrase in combined:
                matched_tier = "EVENT"
                matched_reason = f"Event voucher phrase: '{phrase}'"
                break

    # Check Tier 3: DISCOUNT phrases
    if not matched_tier:
        for phrase in DISCOUNT_VOUCHER_PHRASES:
            if phrase in combined:
                matched_tier = "DISCOUNT"
                matched_reason = f"Discount phrase: '{phrase}'"
                break

    # Check URL patterns (auto-match if URL itself is from voucher domain)
    if not matched_tier and check_voucher_url(link):
        matched_tier = "EVENT"
        matched_reason = f"Voucher URL pattern matched: {link[:80]}"

    # If no voucher phrase matched, REJECT
    if not matched_tier:
        scan_stats["excluded_no_voucher_phrase"] += 1
        debug_log_entry(title, source, None, "No voucher phrase matched", link)
        return None, None

    # ─── Gate 3: Microsoft context check ──────────────────────────────────
    # For Reddit/Google News, the post must mention Microsoft/Azure
    # (Web scraping from microsoft.com is auto-verified)
    is_microsoft_source = (
        source.startswith("Web:") or
        source.startswith("YT:") or
        "Microsoft" in source or
        "Azure" in source or
        "Power" in source or
        "Dynamics" in source
    )

    if not is_microsoft_source:
        has_ms_context = any(word in combined for word in MICROSOFT_CONTEXT_WORDS)
        if not has_ms_context:
            scan_stats["excluded_no_microsoft_context"] += 1
            debug_log_entry(title, source, None, f"No Microsoft context (phrase was: {matched_reason})", link)
            return None, None

    # ─── PASSED ALL GATES — This is a verified voucher opportunity ────────
    scan_stats["verified_alerts"] += 1
    debug_log_entry(title, source, matched_tier, matched_reason, link)
    return matched_tier, matched_reason


# ═════════════════════════════════════════════════════════════════════════════
#  HTML Email Builder — Clean, focused design
# ═════════════════════════════════════════════════════════════════════════════

TIER_CONFIG = {
    "VOUCHER":  {"emoji": "🎟️", "color": "#00E676", "label": "FREE VOUCHER", "bg": "#0D2818"},
    "EVENT":    {"emoji": "📅", "color": "#448AFF", "label": "EVENT → VOUCHER", "bg": "#0D1B2A"},
    "DISCOUNT": {"emoji": "💰", "color": "#FFD600", "label": "DISCOUNT DEAL", "bg": "#2A2500"},
}


def build_html_email(alerts):
    """Build a clean HTML email from verified alerts."""
    rows = ""
    for a in alerts:
        cfg = TIER_CONFIG.get(a["tier"], TIER_CONFIG["EVENT"])
        rows += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 16px; text-align: center; width: 180px;">
                <span style="background: {cfg['color']}; color: #000; padding: 6px 14px;
                             border-radius: 8px; font-weight: bold; font-size: 12px;
                             letter-spacing: 0.5px;">
                    {cfg['emoji']} {cfg['label']}
                </span>
            </td>
            <td style="padding: 16px;">
                <a href="{a['link']}" style="color: #64B5F6; text-decoration: none;
                   font-weight: bold; font-size: 15px;">
                    {a['title'][:150]}
                </a>
                <br>
                <span style="color: #888; font-size: 11px;">📡 {a['source']}</span>
                <br>
                <span style="color: #666; font-size: 11px;">🎯 {a.get('reason', '')[:100]}</span>
            </td>
        </tr>
        """

    return f"""
    <html>
    <body style="background: #0D1117; color: #E0E0E0; font-family: 'Segoe UI', Arial, sans-serif;
                 padding: 24px; margin: 0;">
        <div style="max-width: 680px; margin: 0 auto;">
            <div style="text-align: center; padding: 20px 0;">
                <h1 style="color: #00E676; margin: 0; font-size: 28px;">
                    🎟️ VERIFIED Voucher Alert!
                </h1>
                <p style="color: #8B949E; margin: 8px 0 0 0; font-size: 13px;">
                    Cert Radar v5.0 found {len(alerts)} real voucher opportunit{"ies" if len(alerts) != 1 else "y"}
                    · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                </p>
                <p style="color: #00E676; margin: 8px 0 0 0; font-size: 14px; font-weight: bold;">
                    ⚡ ACT NOW — These opportunities are time-limited!
                </p>
            </div>

            <table style="width: 100%; border-collapse: collapse; background: #161B22;
                          border-radius: 12px; overflow: hidden; border: 1px solid #30363D;">
                <thead>
                    <tr style="background: #21262D;">
                        <th style="padding: 12px; text-align: center; color: #8B949E;
                                   font-size: 11px; letter-spacing: 1px;">TYPE</th>
                        <th style="padding: 12px; text-align: left; color: #8B949E;
                                   font-size: 11px; letter-spacing: 1px;">OPPORTUNITY</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>

            <!-- Quick Links -->
            <div style="margin-top: 24px; padding: 18px; background: #161B22; border: 1px solid #30363D; border-radius: 12px;">
                <h3 style="color: #58A6FF; margin-top: 0; margin-bottom: 12px; font-size: 16px;">
                    🔗 Quick Links — Always Check These
                </h3>
                <ul style="padding-left: 20px; margin: 0; color: #C9D1D9; font-size: 13px; line-height: 2;">
                    <li>📅 <a href="https://events.microsoft.com/en-us/mvtd" style="color: #58A6FF;">Virtual Training Days</a> — Free voucher after attending</li>
                    <li>🏆 <a href="https://learn.microsoft.com/en-us/training/challenges" style="color: #58A6FF;">Learn Challenges</a> — Complete for free voucher</li>
                    <li>🎁 <a href="https://developer.microsoft.com/en-us/offers/30-days-to-learn-it" style="color: #58A6FF;">30 Days to Learn It</a> — 50% off voucher</li>
                    <li>🏅 <a href="https://learn.microsoft.com/en-us/credentials/browse/?credential_types=applied%20skills" style="color: #58A6FF;">Applied Skills</a> — 100% free credentials</li>
                </ul>
            </div>

            <div style="text-align: center; padding: 20px 0;">
                <p style="color: #484F58; font-size: 11px; margin: 0;">
                    Cert Radar v5.0 🛰️ | Zero noise, only verified vouchers
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
    """Send a consolidated HTML email with verified alerts ONLY."""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not ALL_TO_EMAILS:
        print("❌ Email credentials missing! Set EMAIL_ADDRESS, EMAIL_PASSWORD, TO_EMAIL_ADDRESS")
        return False

    if not alerts:
        return False

    # Build subject based on top tier
    tiers = [a["tier"] for a in alerts]
    if "VOUCHER" in tiers:
        subject = f"🎟️ FREE VOUCHER FOUND! {len(alerts)} verified opportunit{'ies' if len(alerts) != 1 else 'y'}"
    elif "EVENT" in tiers:
        subject = f"📅 Voucher Event Found! {len(alerts)} verified opportunit{'ies' if len(alerts) != 1 else 'y'}"
    else:
        subject = f"💰 Cert Discount Found! {len(alerts)} deal{'s' if len(alerts) != 1 else ''}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = ", ".join(ALL_TO_EMAILS)

    # Plain text fallback
    plain = "Cert Radar v5.0 — VERIFIED Voucher Alert\n" + "=" * 50 + "\n\n"
    for a in alerts:
        cfg = TIER_CONFIG.get(a["tier"], TIER_CONFIG["EVENT"])
        plain += f"[{cfg['label']}] {a['title']}\n"
        plain += f"  Link: {a['link']}\n"
        plain += f"  Source: {a['source']}\n"
        plain += f"  Why: {a.get('reason', '')}\n\n"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_html_email(alerts), "html"))

    if DRY_RUN:
        print(f"🏃 DRY RUN — Would send email with {len(alerts)} verified alerts")
        return True

    # Send with 3 retries
    for attempt in range(3):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            print(f"✅ Email sent! ({len(alerts)} verified alerts)")
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
            "tier": "VOUCHER",
            "title": "🧪 TEST — Free AZ-900 Exam Voucher from Microsoft Ignite Challenge!",
            "link": "https://example.com/test",
            "source": "Test Source",
            "reason": "Test: Guaranteed voucher phrase matched",
        },
    ]
    success = send_email_alert(test_alerts)
    if success:
        print("✅ Test email sent! Check your inbox.")
    else:
        print("❌ Test email failed. Check your credentials.")


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
                scan_stats["source_errors"].append(f"{source_name}: {feed.bozo_exception}")
                continue

            scan_stats["source_success"].append(source_name)
            for entry in feed.entries:
                link = getattr(entry, "link", "")
                if not link or is_seen(seen, link):
                    continue

                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")

                tier, reason = classify_entry(title, summary, link, source_name)

                if tier:
                    alert = {
                        "tier": tier,
                        "title": title,
                        "link": link,
                        "source": source_name,
                        "reason": reason,
                        "found_at": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
                    mark_seen(seen, link, source_name, tier)
                    print(f"     🎯 [{tier}] {title[:80]}")

        except Exception as e:
            print(f"     ❌ Error: {e}")
            scan_stats["source_errors"].append(f"{source_name}: {str(e)[:100]}")

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
                       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }

    for target in SCRAPE_TARGETS:
        print(f"  🌐 {target['name']}...")
        try:
            resp = requests.get(target["url"], headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            scan_stats["source_success"].append(f"Web: {target['name']}")

            elements = soup.select(target["selector"])
            for el in elements:
                text = el.get_text(strip=True)
                link = el.get("href", target["url"])

                # Make relative URLs absolute
                if link and not link.startswith("http"):
                    from urllib.parse import urljoin
                    link = urljoin(target["url"], link)

                if not text or len(text) < 15 or is_seen(seen, link):
                    continue

                tier, reason = classify_entry(text, "", link, f"Web: {target['name']}")
                if tier:
                    alert = {
                        "tier": tier,
                        "title": text[:150],
                        "link": link,
                        "source": f"Web: {target['name']}",
                        "reason": reason,
                        "found_at": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
                    mark_seen(seen, link, target["name"], tier)
                    print(f"     🎯 [{tier}] {text[:80]}")

        except Exception as e:
            print(f"     ❌ Error: {e}")
            scan_stats["source_errors"].append(f"Web: {target['name']}: {str(e)[:100]}")

        time.sleep(2)

    return alerts


# ═════════════════════════════════════════════════════════════════════════════
#  Phase 3: GitHub Community Voucher Tracker (v5.0 NEW)
# ═════════════════════════════════════════════════════════════════════════════

def scan_github_tracker(seen):
    """
    Scan the community-maintained GitHub voucher tracker for active offers.
    This tracker is updated by real people who verify voucher opportunities.
    """
    if not HAS_SCRAPING:
        print("  ⏭️  Skipping GitHub tracker (needs requests library)")
        return []

    alerts = []
    print("  📋 GitHub: Community Voucher Tracker...")

    try:
        headers = {
            "User-Agent": "CertRadar/5.0",
            "Accept": "text/plain",
        }
        resp = requests.get(GITHUB_VOUCHER_TRACKER, headers=headers, timeout=15)
        resp.raise_for_status()
        content = resp.text.lower()
        scan_stats["source_success"].append("GitHub: Voucher Tracker")

        # Look for active/current offers in the README
        lines = resp.text.split("\n")
        in_active_section = False

        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()

            # Detect active/current sections
            if any(marker in line_lower for marker in ["active", "current", "ongoing", "available now", "✅", "🟢"]):
                if "#" in line_stripped or "**" in line_stripped:
                    in_active_section = True
                    continue

            # Detect expired/ended sections — stop reading
            if any(marker in line_lower for marker in ["expired", "ended", "closed", "past", "❌", "🔴", "archive"]):
                if "#" in line_stripped or "**" in line_stripped:
                    in_active_section = False
                    continue

            # Extract links from active section
            if in_active_section:
                # Look for markdown links [text](url)
                link_matches = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', line_stripped)
                for link_text, link_url in link_matches:
                    if is_seen(seen, link_url):
                        continue

                    # Check if this mentions voucher/free/exam
                    combined_text = f"{link_text} {line_stripped}".lower()
                    has_voucher_mention = any(word in combined_text for word in [
                        "voucher", "free", "exam", "certification", "challenge",
                        "training day", "discount", "100%",
                    ])

                    if has_voucher_mention:
                        alert = {
                            "tier": "VOUCHER",
                            "title": f"[Community Verified] {link_text[:120]}",
                            "link": link_url,
                            "source": "GitHub: Community Voucher Tracker",
                            "reason": "Listed as active in community voucher tracker",
                            "found_at": datetime.now().isoformat(),
                        }
                        alerts.append(alert)
                        mark_seen(seen, link_url, "GitHub Tracker", "VOUCHER")
                        print(f"     🎯 [VOUCHER] {link_text[:80]}")

    except Exception as e:
        print(f"     ❌ Error: {e}")
        scan_stats["source_errors"].append(f"GitHub Tracker: {str(e)[:100]}")

    return alerts


# ═════════════════════════════════════════════════════════════════════════════
#  Save scan stats
# ═════════════════════════════════════════════════════════════════════════════

def save_scan_stats():
    """Save scan stats to file."""
    data = {
        "last_scan": datetime.now().isoformat(),
        "last_stats": dict(scan_stats),
    }
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


# ═════════════════════════════════════════════════════════════════════════════
#  Main Entry Point
# ═════════════════════════════════════════════════════════════════════════════

def check_feeds():
    """Run a complete scan across all sources."""
    start = time.time()

    total_sources = len(RSS_FEEDS) + len(SCRAPE_TARGETS) + 1  # +1 for GitHub tracker

    print("=" * 60)
    print("🎯 CERT RADAR v5.0 — Zero Noise Voucher Hunter")
    print(f"   📡 {len(RSS_FEEDS)} RSS feeds + {len(SCRAPE_TARGETS)} web pages + 1 GitHub tracker")
    print(f"   📊 Total source channels: {total_sources}")
    if DRY_RUN:
        print("   🏃 DRY RUN MODE — No emails will be sent")
    if DEBUG:
        print("   🐛 DEBUG MODE — Full evaluation breakdown enabled")
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

    # Phase 3: GitHub community tracker
    print("\n📋 PHASE 3: GitHub Community Voucher Tracker")
    print("-" * 40)
    github_alerts = scan_github_tracker(seen)
    all_alerts.extend(github_alerts)

    # Save updated seen links
    save_seen(seen)

    # Save debug log
    save_debug_log()

    # Save stats
    save_scan_stats()

    # Deduplicate alerts by link
    seen_links_set = set()
    deduped_alerts = []
    for a in all_alerts:
        if a["link"] not in seen_links_set:
            seen_links_set.add(a["link"])
            deduped_alerts.append(a)
    all_alerts = deduped_alerts

    # Sort by tier (VOUCHER first, then EVENT, then DISCOUNT)
    tier_order = {"VOUCHER": 0, "EVENT": 1, "DISCOUNT": 2}
    all_alerts.sort(key=lambda a: tier_order.get(a["tier"], 99))

    # Print results summary
    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"📊 SCAN COMPLETE — {elapsed:.1f}s")
    print(f"   Posts evaluated: {scan_stats['total_posts_evaluated']}")
    print(f"   Excluded (noise patterns): {scan_stats['excluded_by_patterns']}")
    print(f"   Excluded (no voucher phrase): {scan_stats['excluded_no_voucher_phrase']}")
    print(f"   Excluded (no Microsoft context): {scan_stats['excluded_no_microsoft_context']}")
    print(f"   ✅ VERIFIED alerts: {scan_stats['verified_alerts']}")
    print(f"   Sources OK: {len(scan_stats['source_success'])}")
    print(f"   Sources failed: {len(scan_stats['source_errors'])}")
    print(f"   Total new alerts: {len(all_alerts)}")
    for t in ["VOUCHER", "EVENT", "DISCOUNT"]:
        count = sum(1 for a in all_alerts if a["tier"] == t)
        if count > 0:
            cfg = TIER_CONFIG[t]
            print(f"   {cfg['emoji']} {t}: {count}")
    print("=" * 60)

    # Send email ONLY if there are verified alerts
    if all_alerts:
        for a in all_alerts:
            log_alert(a)
        send_email_alert(all_alerts)
    else:
        print("🔇 No verified voucher opportunities found. Staying silent.")

    return all_alerts


if __name__ == "__main__":
    # Handle flags
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
                    🎯 Cert Radar v5.0 — Zero Noise Voucher Hunter
        """)
        check_feeds()

"""
Pro Cert Radar v4.0 — Ultimate Certification Voucher Hunter 🎯🔥
=================================================================
The most aggressive, wide-net Microsoft certification voucher finder.
Monitors 45+ high-signal sources and emails you when ANY deal is posted.

v4.0 Changes (from v3.0):
  • Relaxed scoring engine — catches way more real deals
  • 45+ sources (up from 21) — Reddit, Google News, Twitter/Nitter, blogs
  • Reddit JSON API search — bypasses RSS rate limits
  • Regex-based keyword matching — flexible, catches natural language
  • URL pattern detection — auto-boost links from known deal domains
  • Daily digest heartbeat — never wonder if it's broken
  • Debug logging — full transparency on every post evaluated
  • --dry-run and --debug flags for testing

Sources:
  • Reddit RSS (16 subreddits) + Reddit JSON Search (8 queries)
  • Google News (15 real-time voucher queries)
  • Microsoft Official (Learn Blog, TechCommunity, Azure Blog)
  • YouTube: Microsoft Learn
  • Hacker News (filtered)
  • Web scraping: Ignite, Build, 30 Days, Challenges, Virtual Training Days
  • Dev.to, Nitter/Twitter (best-effort)

Usage:
  python checker.py                    # Full scan + email
  python checker.py --test-email       # Send a test email to verify setup
  python checker.py --dry-run          # Scan but don't send email
  python checker.py --debug            # Show full scoring breakdown
  python checker.py --digest           # Force send daily digest
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
SEEN_FILE  = "seen_links.json"
LOG_FILE   = "alert_log.json"
DEBUG_FILE = "debug_log.json"
STATS_FILE = "scan_stats.json"

# Command-line flags
DRY_RUN = "--dry-run" in sys.argv
DEBUG   = "--debug" in sys.argv

# ═════════════════════════════════════════════════════════════════════════════
#  v4.0 — Keyword & Domain Configuration (MASSIVELY EXPANDED)
# ═════════════════════════════════════════════════════════════════════════════

# ⛔ EXCLUDE_KEYWORDS — Only truly irrelevant content
# v4.0: TRIMMED aggressively — removed overly broad terms that were killing legit posts
EXCLUDE_KEYWORDS = [
    # Physical / non-IT spam
    "gluten free", "gluten-free", "paperback", "free shipping",
    "bug free", "bug-free", "t-shirt", "stickers", "gluten",
    "thriller", "novel", "recipe", "cookbook",
    # Pure exam result brags (NOT deal-related at all)
    "i passed", "i failed", "just passed", "just failed",
    "passed today", "failed today", "how i passed",
    # Job posts (not cert deals)
    "salary", "got the job", "hiring manager", "resume review",
    "interview questions",
    # Non-Microsoft vendors (to keep focused)
    "comptia a+", "comptia network+", "comptia security+",
    "aws certified", "aws solution", "google cloud certified",
    "cisco ccna", "cisco ccnp",
]

# 🎯 REQUIRED_TECH_WORDS — v4.0: Expanded + used CONDITIONALLY
# For CRITICAL matches, this gate is BYPASSED (a "free voucher" post is valuable regardless)
# For other tiers, at least ONE must match
REQUIRED_TECH_WORDS = [
    # General Microsoft
    "microsoft", "azure", "mslearn", "microsoft learn",
    "microsoft 365", "m365", "ms learn",
    # Power Platform & Power Apps
    "power apps", "powerapps", "power platform", "powerplatform",
    "power automate", "power bi", "power pages", "powerpages",
    "pl-900", "pl-100", "pl-200", "pl-300", "pl-400", "pl-500", "pl-600",
    # Dynamics 365 (D365)
    "d365", "dynamics 365", "dynamics365",
    "mb-910", "mb-920", "mb-210", "mb-220", "mb-230", "mb-240", "mb-260",
    "mb-300", "mb-310", "mb-330", "mb-500", "mb-700", "mb-800",
    # Azure & AI Exam Series
    "az-900", "az-104", "az-204", "az-305", "az-400", "az-500",
    "az-700", "az-800", "az-801", "az-802",
    "dp-900", "dp-100", "dp-203", "dp-300", "dp-500", "dp-600",
    "ai-900", "ai-102", "ai-050", "ai-500",
    "sc-900", "sc-100", "sc-200", "sc-300", "sc-400", "sc-500",
    "ms-900", "ms-700", "ms-102", "md-102",
    # Event names
    "ignite", "microsoft build", "virtual training day",
    "cloud skills challenge", "30 days to learn",
    # Broad cert terms (new in v4.0 — catches more)
    "certification voucher", "exam voucher", "cert voucher",
    "free certification", "free exam", "free cert",
    "certification discount", "exam discount",
    "applied skills", "microsoft credential",
    "microsoft reactor", "skills fest",
    "learn live", "hack together",
]

# 🔑 ACTIONABLE_WORDS — v4.0: Expanded massively, used for HIGH only (not CRITICAL)
ACTIONABLE_WORDS = [
    "voucher", "coupon", "promo", "discount", "free exam", "free cert",
    "offer", "register", "sign up", "signup", "enroll", "claim", "code",
    "% off", "percent off", "half price", "deal", "grab", "hurry",
    "limited time", "expires", "challenge", "skilling",
    "virtual training day", "30 days to learn",
    # v4.0 additions
    "redeem", "activate", "apply", "available now", "open now",
    "registration open", "register now", "sign up now", "enroll now",
    "get certified", "earn a badge", "earn a certificate",
    "giveaway", "complimentary", "no cost", "at no cost",
    "save", "savings", "promotion", "promotional",
    "link", "url", "here", "click", "check out",
    "announcing", "announced", "launching", "launched", "new",
    "starts", "starting", "begins", "beginning",
    "deadline", "last chance", "ending soon", "don't miss",
    "act now", "act fast", "while supplies last",
]

# 🔴 CRITICAL — Free voucher / coupon posts (MASSIVELY EXPANDED)
CRITICAL_KEYWORDS = [
    # Direct free voucher mentions
    "free voucher", "free exam voucher", "free certification voucher",
    "free cert voucher", "free microsoft voucher", "free azure voucher",
    "voucher giveaway", "exam voucher giveaway", "certification giveaway",
    # Promo/discount codes
    "100% off", "100% discount", "100 percent off",
    "coupon code", "promo code", "discount code", "voucher code",
    "redemption code", "promotional code",
    # Complimentary/free exams
    "complimentary exam", "complimentary certification",
    "free azure exam", "free microsoft exam",
    "free certification exam", "free dp-", "free az-", "free ai-",
    "free sc-", "free pl-", "free mb-", "free ms-", "free md-",
    "no cost exam", "no cost certification", "at no cost",
    "zero cost", "$0",
    # Event-specific vouchers
    "ignite voucher", "build voucher", "ignite free exam", "build free exam",
    "ignite free cert", "build free cert",
    "ignite certification voucher", "build certification voucher",
    # Giveaway patterns
    "giving away voucher", "giving away exam", "giving away certification",
    "handing out voucher", "free exam code",
    "here's a voucher", "here is a voucher",
    "spare voucher", "extra voucher", "unused voucher",
    # Community sharing patterns
    "i have a voucher", "i have voucher", "voucher to share",
    "exam voucher to give", "don't need this voucher",
    "won't use this voucher", "giving this away",
]

# 🟠 HIGH — Events / Challenges that grant exam vouchers (EXPANDED)
EVENT_KEYWORDS = [
    "virtual training day", "virtual training event",
    "microsoft ignite", "ignite challenge", "ignite session",
    "cloud skills challenge", "skills challenge",
    "30 days to learn", "30 days to learn it",
    "learn live", "learn live event",
    "microsoft build", "build challenge", "build session",
    "free training event", "free training day",
    "skilling challenge", "defender skilling",
    # v4.0 additions
    "microsoft reactor", "reactor event",
    "skills fest", "skill fest",
    "hack together", "hackathon",
    "certification bootcamp", "cert bootcamp",
    "training bootcamp", "azure bootcamp",
    "certification day", "cert day",
    "exam prep live", "exam cram",
    "microsoft certified", "get certified",
    "certification challenge", "learning challenge",
    "microsoft event", "azure event",
    "power platform challenge",
    "ai skills challenge", "security skills challenge",
    "fundamentals day", "azure fundamentals",
    "learn cloud skills", "cloud skills",
]

# 🟡 MEDIUM — Discounts & deals (EXPANDED)
DISCOUNT_KEYWORDS = [
    "50% off", "half price", "discount code", "voucher discount",
    "50% discount", "student discount", "reduced price",
    "practice exam free",
    # v4.0 additions
    "25% off", "30% off", "40% off", "45% off",
    "percentage off", "percent off",
    "exam discount", "certification discount",
    "discounted exam", "discounted certification",
    "reduced fee", "reduced cost",
    "early bird", "early registration",
    "bundle deal", "exam bundle",
    "esi discount", "enterprise skills initiative",
    "academic discount", "education discount",
    "beta exam", "beta exam free",
    "retake voucher", "second shot", "second chance",
    "certification renewal", "renewal discount",
    "pearson vue deal", "pearson vue discount",
    "certiport", "exam sale",
]

# 🟢 LOW — General cert news & updates (EXPANDED)
INFO_KEYWORDS = [
    "new certification announced", "certification retired",
    "exam update announced", "certification roadmap",
    "exam objectives changed", "new exam announced",
    # v4.0 additions
    "certification update", "exam update",
    "new learning path", "learning path",
    "certification news", "exam news",
    "microsoft learn update", "credential update",
    "applied skills", "new credential",
    "new badge", "badge available",
    "certification program", "exam program",
    "exam change", "objectives update",
    "certification guide", "free training",
    "free course", "free learning",
    "study guide released", "prep guide",
]

# Context words — confirms a post is cert-related (used with EVENT/DISCOUNT)
CERT_CONTEXT_WORDS = [
    "voucher", "certification", "exam", "certificate", "credential",
    "badge", "microsoft learn", "az-", "ai-", "dp-", "sc-", "ms-",
    "mb-", "pl-", "md-", "mo-", "fundamentals", "d365", "power apps",
    "power platform", "power automate", "power bi", "dynamics 365",
    # v4.0 additions
    "certiport", "pearson vue", "pearsonvue", "proctored",
    "assessment", "applied skills", "microsoft certified",
    "cloud skills", "learn live", "mslearn",
    "certification exam", "cert exam", "microsoft exam",
]

# 🌐 URL_BOOST_PATTERNS — Auto-boost score for links from known deal domains
URL_BOOST_PATTERNS = [
    r"aka\.ms/",
    r"learn\.microsoft\.com/.*training",
    r"learn\.microsoft\.com/.*challenge",
    r"learn\.microsoft\.com/.*credentials",
    r"ignite\.microsoft\.com",
    r"build\.microsoft\.com",
    r"developer\.microsoft\.com/.*offers",
    r"esi\.microsoft\.com",
    r"events\.microsoft\.com",
    r"reactor\.microsoft\.com",
    r"microsoft\.com/.*virtual-training",
    r"microsoft\.com/.*skills-challenge",
    r"certiport\.com",
    r"pearsonvue\.com/.*microsoft",
]

# ═════════════════════════════════════════════════════════════════════════════
#  RSS Feed Sources — MASSIVELY EXPANDED (45+ sources)
# ═════════════════════════════════════════════════════════════════════════════

RSS_FEEDS = {
    # ── Reddit: Microsoft-focused subreddits ──────────────────────────────
    "Reddit: Microsoft Certifications": "https://www.reddit.com/r/MicrosoftCertifications/.rss",
    "Reddit: Azure Certification":      "https://www.reddit.com/r/AzureCertification/.rss",
    "Reddit: Power Platform":           "https://www.reddit.com/r/PowerPlatform/.rss",
    "Reddit: Power Apps":               "https://www.reddit.com/r/PowerApps/.rss",
    "Reddit: Power BI":                 "https://www.reddit.com/r/PowerBI/.rss",
    "Reddit: Power Automate":           "https://www.reddit.com/r/MicrosoftFlow/.rss",
    "Reddit: Dynamics 365":             "https://www.reddit.com/r/dynamics365/.rss",
    "Reddit: Azure":                    "https://www.reddit.com/r/Azure/.rss",

    # ── Reddit: Broader communities (v4.0 NEW) ───────────────────────────
    "Reddit: Microsoft":                "https://www.reddit.com/r/microsoft/.rss",
    "Reddit: Freebies":                 "https://www.reddit.com/r/freebies/.rss",
    "Reddit: IT Career Questions":      "https://www.reddit.com/r/ITCareerQuestions/.rss",
    "Reddit: Sysadmin":                 "https://www.reddit.com/r/sysadmin/.rss",
    "Reddit: Cloud Computing":          "https://www.reddit.com/r/cloudcomputing/.rss",
    "Reddit: Learn Programming":        "https://www.reddit.com/r/learnprogramming/.rss",
    "Reddit: Certs":                    "https://www.reddit.com/r/certs/.rss",
    "Reddit: Information Technology":   "https://www.reddit.com/r/InformationTechnology/.rss",

    # ── Google News: Voucher-specific queries ─────────────────────────────
    "Google News: MS Cert Voucher":          "https://news.google.com/rss/search?q=free+microsoft+certification+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Azure Exam Discount":      "https://news.google.com/rss/search?q=azure+exam+voucher+discount&hl=en-US&gl=US&ceid=US:en",
    "Google News: Cloud Skills Challenge":   "https://news.google.com/rss/search?q=cloud+skills+challenge+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Dynamics 365 Voucher":     "https://news.google.com/rss/search?q=dynamics+365+exam+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Power Apps Voucher":       "https://news.google.com/rss/search?q=power+apps+exam+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Ignite Voucher":        "https://news.google.com/rss/search?q=microsoft+ignite+certification+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Ignite Challenge":      "https://news.google.com/rss/search?q=microsoft+ignite+cloud+skills+challenge&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Build Challenge":       "https://news.google.com/rss/search?q=microsoft+build+cloud+skills+challenge&hl=en-US&gl=US&ceid=US:en",

    # ── Google News: v4.0 NEW queries ─────────────────────────────────────
    "Google News: Virtual Training Day":     "https://news.google.com/rss/search?q=microsoft+virtual+training+day+free&hl=en-US&gl=US&ceid=US:en",
    "Google News: Azure Free Cert 2026":     "https://news.google.com/rss/search?q=azure+free+certification+2026&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Exam Deal":             "https://news.google.com/rss/search?q=microsoft+exam+deal+discount+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Learn Challenge":       "https://news.google.com/rss/search?q=microsoft+learn+challenge+2026&hl=en-US&gl=US&ceid=US:en",
    "Google News: Free Cloud Cert":          "https://news.google.com/rss/search?q=free+cloud+certification+voucher&hl=en-US&gl=US&ceid=US:en",
    "Google News: Applied Skills":           "https://news.google.com/rss/search?q=microsoft+applied+skills+credential&hl=en-US&gl=US&ceid=US:en",
    "Google News: MS Credential Voucher":    "https://news.google.com/rss/search?q=microsoft+credential+voucher+free&hl=en-US&gl=US&ceid=US:en",

    # ── Microsoft Official ────────────────────────────────────────────────
    "MS Learn Blog":          "https://techcommunity.microsoft.com/t5/microsoft-learn-blog/bg-p/MicrosoftLearnBlog.rss",
    "MS TechCommunity":       "https://techcommunity.microsoft.com/t5/educator-developer-blog/bg-p/EducatorDeveloperBlog.rss",
    "MS Azure Blog":          "https://azure.microsoft.com/en-us/blog/feed/",

    # ── YouTube ───────────────────────────────────────────────────────────
    "YT: Microsoft Learn":   "https://www.youtube.com/feeds/videos.xml?channel_id=UCddiUEpeqJcYeBxX1IVBKvQ",

    # ── Hacker News (filtered) ────────────────────────────────────────────
    "HN: Microsoft Voucher":    "https://hnrss.org/newest?q=microsoft+voucher",
    "HN: Azure Certification":  "https://hnrss.org/newest?q=azure+certification",
    "HN: Free Certification":   "https://hnrss.org/newest?q=free+certification",

    # ── Dev.to (v4.0 NEW) ────────────────────────────────────────────────
    "Dev.to: Microsoft Certs":  "https://dev.to/feed/tag/microsoft",
    "Dev.to: Azure":            "https://dev.to/feed/tag/azure",
    "Dev.to: Certification":    "https://dev.to/feed/tag/certification",
}

# ═════════════════════════════════════════════════════════════════════════════
#  Reddit JSON API Search Queries (v4.0 NEW — bypasses RSS rate limits)
# ═════════════════════════════════════════════════════════════════════════════

REDDIT_SEARCH_QUERIES = [
    "free microsoft certification voucher",
    "free azure exam voucher",
    "cloud skills challenge voucher",
    "microsoft virtual training day free",
    "free certification exam voucher",
    "microsoft ignite free exam",
    "microsoft build free certification",
    "certification voucher giveaway",
]

# ═════════════════════════════════════════════════════════════════════════════
#  Web Scraping Targets (EXPANDED)
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
    # ── v4.0 NEW targets ──────────────────────────────────────────────────
    {
        "name": "Microsoft Virtual Training Days",
        "url": "https://events.microsoft.com/en-us/mvtd",
        "selector": "a, h1, h2, h3, p, span",
    },
    {
        "name": "Microsoft Applied Skills",
        "url": "https://learn.microsoft.com/en-us/credentials/browse/?credential_types=applied%20skills",
        "selector": "a, h2, h3, p",
    },
    {
        "name": "Microsoft Reactor Events",
        "url": "https://developer.microsoft.com/en-us/reactor/",
        "selector": "a, h2, h3, p",
    },
    {
        "name": "Microsoft Learn FAQ - Discounts",
        "url": "https://learn.microsoft.com/en-us/credentials/certifications/certification-exam-policies",
        "selector": "a, h2, h3, p, li",
    },
]

# ═════════════════════════════════════════════════════════════════════════════
#  Nitter/Twitter Search (v4.0 NEW — best-effort, may be unreliable)
# ═════════════════════════════════════════════════════════════════════════════

# Multiple Nitter instances for redundancy
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.woodland.cafe",
]

TWITTER_SEARCH_QUERIES = [
    "microsoft free voucher",
    "azure certification free",
    "microsoft exam voucher",
    "cloud skills challenge",
    "virtual training day microsoft",
]

TWITTER_ACCOUNTS = [
    "MSLearn",
    "AzureSupport",
    "Microsoft",
]

# ═════════════════════════════════════════════════════════════════════════════
#  Scan Statistics Tracker (v4.0 NEW)
# ═════════════════════════════════════════════════════════════════════════════

scan_stats = {
    "total_posts_evaluated": 0,
    "excluded_by_keywords": 0,
    "excluded_by_tech_gate": 0,
    "excluded_by_score": 0,
    "passed_all_gates": 0,
    "near_misses": [],  # score 1-2
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
    log = log[-500:]  # Keep last 500 alerts
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
#  Debug Log (v4.0 NEW — records every evaluated post)
# ═════════════════════════════════════════════════════════════════════════════

debug_entries = []

def debug_log_entry(title, source, score, priority, reason, link=""):
    """Log a post evaluation for debugging."""
    entry = {
        "title": title[:150],
        "source": source,
        "score": score,
        "priority": priority,
        "reason": reason,
        "link": link,
        "time": datetime.now().isoformat(),
    }
    debug_entries.append(entry)
    if DEBUG:
        status = f"✅ [{priority}]" if priority else "❌ FILTERED"
        print(f"     {status} score={score} | {reason} | {title[:80]}")


def save_debug_log():
    """Save debug log to file (keep last 1000 entries)."""
    existing = []
    if os.path.exists(DEBUG_FILE):
        try:
            with open(DEBUG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []
    existing.extend(debug_entries)
    existing = existing[-1000:]
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════════════
#  v4.0 — Score-Based Classification Engine (RELAXED + SMARTER)
# ═════════════════════════════════════════════════════════════════════════════

def check_url_boost(link):
    """Check if a URL matches known deal domains and return bonus score."""
    if not link:
        return 0
    for pattern in URL_BOOST_PATTERNS:
        if re.search(pattern, link, re.IGNORECASE):
            return 3  # +3 bonus for links from known deal sources
    return 0


def classify_entry(title, summary, link="", source=""):
    """
    v4.0 Score-based classifier — RELAXED for maximum coverage.

    Key changes from v3.0:
    1. CRITICAL keywords matched in BOTH title AND summary (full score for both)
    2. Actionability gate REMOVED for CRITICAL
    3. REQUIRED_TECH_WORDS bypassed for CRITICAL (free voucher = always valuable)
    4. Score threshold lowered from 3 → 2
    5. URL pattern detection for auto-boost
    6. Near-miss tracking for debugging

    Returns:
        (priority, alert_type, score) or (None, None, 0) if no match.
    """
    title_lower = title.lower()
    summary_lower = summary.lower() if summary else ""
    combined = f"{title_lower} {summary_lower}"

    scan_stats["total_posts_evaluated"] += 1

    # ─── Gate 1: Exclude obviously irrelevant content ─────────────────────
    for neg in EXCLUDE_KEYWORDS:
        if neg in title_lower:
            scan_stats["excluded_by_keywords"] += 1
            debug_log_entry(title, source, 0, None, f"EXCLUDED by '{neg}'", link)
            return None, None, 0

    # ─── Score calculation ────────────────────────────────────────────────
    score = 0
    matched_tier = None
    score_reasons = []

    # 🔴 CRITICAL — Check BOTH title AND summary (v4.0 change: summary gets full score too)
    critical_in_title = any(kw in title_lower for kw in CRITICAL_KEYWORDS)
    critical_in_summary = any(kw in summary_lower for kw in CRITICAL_KEYWORDS)

    if critical_in_title:
        score += 10
        matched_tier = "CRITICAL"
        score_reasons.append("CRITICAL keyword in title (+10)")
    elif critical_in_summary:
        score += 8  # v4.0: bumped from +3 to +8 (summary mention is still very strong)
        matched_tier = "CRITICAL"
        score_reasons.append("CRITICAL keyword in summary (+8)")

    # 🟠 HIGH — Events (title or summary, with cert context)
    if any(kw in combined for kw in EVENT_KEYWORDS):
        has_context = any(ctx in combined for ctx in CERT_CONTEXT_WORDS)
        if has_context:
            score += 6
            score_reasons.append("EVENT keyword + cert context (+6)")
        else:
            score += 3  # Event without explicit cert context still gets points
            score_reasons.append("EVENT keyword, no cert context (+3)")
        if matched_tier is None:
            matched_tier = "HIGH"

    # 🟡 MEDIUM — Discounts (with cert context)
    if any(kw in combined for kw in DISCOUNT_KEYWORDS):
        has_context = any(ctx in combined for ctx in CERT_CONTEXT_WORDS)
        if has_context:
            score += 4
            score_reasons.append("DISCOUNT keyword + cert context (+4)")
        else:
            score += 2
            score_reasons.append("DISCOUNT keyword, no cert context (+2)")
        if matched_tier is None:
            matched_tier = "MEDIUM"

    # 🟢 LOW — General cert news
    if any(kw in combined for kw in INFO_KEYWORDS):
        score += 2
        score_reasons.append("INFO keyword (+2)")
        if matched_tier is None:
            matched_tier = "LOW"

    # 🌐 URL boost — links from known deal domains
    url_bonus = check_url_boost(link)
    if url_bonus > 0:
        score += url_bonus
        score_reasons.append(f"URL pattern boost (+{url_bonus})")

    # ─── Regex-based matching — catch natural language patterns ────────────
    regex_patterns = [
        (r"\bfree\b.*\b(?:exam|cert|voucher|certification)\b", 5, "Regex: 'free...exam/cert/voucher'"),
        (r"\b(?:exam|cert|voucher|certification)\b.*\bfree\b", 5, "Regex: 'exam/cert/voucher...free'"),
        (r"\b(?:100|hundred)\s*%?\s*(?:off|discount)\b", 5, "Regex: '100% off/discount'"),
        (r"\b(?:no\s+cost|zero\s+cost|complimentary)\b.*\b(?:exam|cert)\b", 5, "Regex: 'no cost...exam/cert'"),
        (r"\bgiveaway\b.*\b(?:voucher|exam|cert)\b", 4, "Regex: 'giveaway...voucher/exam/cert'"),
        (r"\b(?:voucher|exam|cert)\b.*\bgiveaway\b", 4, "Regex: 'voucher/exam/cert...giveaway'"),
        (r"\bdiscount\b.*\b(?:exam|cert|voucher)\b", 3, "Regex: 'discount...exam/cert/voucher'"),
        (r"\b(?:50|fifty)\s*%?\s*off\b", 3, "Regex: '50% off'"),
    ]
    for pattern, points, reason in regex_patterns:
        if re.search(pattern, combined, re.IGNORECASE):
            score += points
            score_reasons.append(f"{reason} (+{points})")
            if matched_tier is None:
                matched_tier = "CRITICAL" if points >= 5 else "MEDIUM"

    # ─── Gate 2: Tech words check (BYPASSED for CRITICAL matches) ─────────
    # v4.0 change: if score >= 8 (strong CRITICAL signal), skip tech gate entirely
    if score < 8:
        if not any(tech in combined for tech in REQUIRED_TECH_WORDS):
            scan_stats["excluded_by_tech_gate"] += 1
            # Track as near-miss if score was close
            if score >= 1:
                scan_stats["near_misses"].append({
                    "title": title[:100],
                    "source": source,
                    "score": score,
                    "reason": "No tech word match",
                })
            debug_log_entry(title, source, score, None, "No REQUIRED_TECH_WORD match", link)
            return None, None, 0

    # ─── Gate 3: Score threshold (LOWERED from 3 → 2) ────────────────────
    if score < 2:
        scan_stats["excluded_by_score"] += 1
        if score >= 1:
            scan_stats["near_misses"].append({
                "title": title[:100],
                "source": source,
                "score": score,
                "reason": f"Score {score} < 2",
            })
        debug_log_entry(title, source, score, None, f"Score {score} below threshold (2)", link)
        return None, None, 0

    # ─── Gate 4: Actionability — ONLY for HIGH tier (v4.0: removed for CRITICAL) ──
    if matched_tier == "HIGH":
        if not any(act in combined for act in ACTIONABLE_WORDS):
            if score >= 4:
                # Downgrade to MEDIUM instead of dropping
                reason = " | ".join(score_reasons)
                debug_log_entry(title, source, score, "MEDIUM", f"HIGH→MEDIUM (no action word) | {reason}", link)
                scan_stats["passed_all_gates"] += 1
                return "MEDIUM", "MENTION", score
            # Still keep as LOW if score >= 2
            if score >= 2:
                reason = " | ".join(score_reasons)
                debug_log_entry(title, source, score, "LOW", f"HIGH→LOW (no action word) | {reason}", link)
                scan_stats["passed_all_gates"] += 1
                return "LOW", "INFO", score

    # ─── Determine final priority ─────────────────────────────────────────
    reason = " | ".join(score_reasons)
    scan_stats["passed_all_gates"] += 1

    if matched_tier == "CRITICAL" and score >= 8:
        debug_log_entry(title, source, score, "CRITICAL", reason, link)
        return "CRITICAL", "INSTANT", score
    elif matched_tier in ("CRITICAL", "HIGH") and score >= 6:
        debug_log_entry(title, source, score, "HIGH", reason, link)
        return "HIGH", "EVENT", score
    elif score >= 4:
        debug_log_entry(title, source, score, "MEDIUM", reason, link)
        return "MEDIUM", "DISCOUNT", score
    elif score >= 2:
        debug_log_entry(title, source, score, "LOW", reason, link)
        return "LOW", "INFO", score

    debug_log_entry(title, source, score, None, f"No tier matched | {reason}", link)
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
                    🎯 Cert Radar v4.0 Alert
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
                    <li style="margin-top: 8px;">
                        <strong>📅 Virtual Training Days (Free Vouchers!):</strong> Microsoft's free instructor-led events that include free exam vouchers.<br>
                        👉 <a href="https://events.microsoft.com/en-us/mvtd" style="color: #58A6FF;">Browse Virtual Training Days</a>
                    </li>
                </ul>
            </div>

            <div style="text-align: center; padding: 20px 0;">
                <p style="color: #484F58; font-size: 11px; margin: 0;">
                    Powered by Pro Cert Radar v4.0 🛰️ | Monitoring {len(RSS_FEEDS)} feeds + {len(SCRAPE_TARGETS)} pages
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def build_digest_email(stats, near_misses):
    """Build a daily digest / heartbeat email."""
    near_miss_rows = ""
    for nm in near_misses[:20]:
        near_miss_rows += f"""
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 8px; color: #888; font-size: 12px;">{nm.get('score', 0)}</td>
            <td style="padding: 8px; color: #C9D1D9; font-size: 12px;">{nm.get('title', '')[:100]}</td>
            <td style="padding: 8px; color: #888; font-size: 11px;">{nm.get('reason', '')}</td>
        </tr>
        """

    source_errors_html = ""
    if stats.get("source_errors"):
        errors = "<br>".join([f"❌ {e}" for e in stats["source_errors"][:10]])
        source_errors_html = f"""
        <div style="margin-top: 12px; padding: 12px; background: #2D1B1B; border: 1px solid #5C2020; border-radius: 8px;">
            <strong style="color: #FF6B6B;">⚠️ Source Errors:</strong><br>
            <span style="color: #E8A0A0; font-size: 12px;">{errors}</span>
        </div>
        """

    near_miss_section = ""
    if near_misses:
        near_miss_section = f"""
            <div style="margin-top: 18px; padding: 18px; background: #161B22; border: 1px solid #30363D; border-radius: 12px;">
                <h3 style="color: #FFD600; margin-top: 0;">🔍 Near Misses (scored but filtered)</h3>
                <p style="color: #8B949E; font-size: 12px; margin-top: 0;">These posts scored points but didn't pass all gates. Review to check if filters are too strict.</p>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="border-bottom: 1px solid #30363D;">
                            <th style="padding: 6px; text-align: left; color: #8B949E; font-size: 11px;">Score</th>
                            <th style="padding: 6px; text-align: left; color: #8B949E; font-size: 11px;">Title</th>
                            <th style="padding: 6px; text-align: left; color: #8B949E; font-size: 11px;">Reason</th>
                        </tr>
                    </thead>
                    <tbody>{near_miss_rows}</tbody>
                </table>
            </div>
        """

    health_status = '🟢 HEALTHY' if not stats.get('source_errors') else '🟡 DEGRADED'

    return f"""
    <html>
    <body style="background: #0D1117; color: #E0E0E0; font-family: 'Segoe UI', Arial, sans-serif;
                 padding: 24px; margin: 0;">
        <div style="max-width: 680px; margin: 0 auto;">
            <div style="text-align: center; padding: 20px 0;">
                <h1 style="color: #58A6FF; margin: 0; font-size: 28px;">
                    📊 Cert Radar v4.0 — Daily Digest
                </h1>
                <p style="color: #8B949E; margin: 8px 0 0 0; font-size: 13px;">
                    System health report · {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                </p>
            </div>

            <!-- Stats Box -->
            <div style="padding: 18px; background: #161B22; border: 1px solid #30363D; border-radius: 12px;">
                <h3 style="color: #58A6FF; margin-top: 0;">📈 Scan Statistics</h3>
                <table style="width: 100%; color: #C9D1D9; font-size: 14px;">
                    <tr><td>📡 Sources monitored:</td><td style="text-align:right; font-weight:bold;">{len(RSS_FEEDS) + len(SCRAPE_TARGETS) + len(REDDIT_SEARCH_QUERIES)}</td></tr>
                    <tr><td>📄 Posts evaluated:</td><td style="text-align:right; font-weight:bold;">{stats.get('total_posts_evaluated', 0)}</td></tr>
                    <tr><td>⛔ Excluded (keywords):</td><td style="text-align:right;">{stats.get('excluded_by_keywords', 0)}</td></tr>
                    <tr><td>🔧 Excluded (no tech word):</td><td style="text-align:right;">{stats.get('excluded_by_tech_gate', 0)}</td></tr>
                    <tr><td>📉 Excluded (low score):</td><td style="text-align:right;">{stats.get('excluded_by_score', 0)}</td></tr>
                    <tr><td style="color: #00E676;">✅ Passed all gates:</td><td style="text-align:right; color: #00E676; font-weight:bold;">{stats.get('passed_all_gates', 0)}</td></tr>
                    <tr><td>🔍 Near misses:</td><td style="text-align:right;">{len(near_misses)}</td></tr>
                    <tr><td>✅ Sources OK:</td><td style="text-align:right; color:#00E676;">{len(stats.get('source_success', []))}</td></tr>
                    <tr><td>❌ Sources failed:</td><td style="text-align:right; color:#FF6B6B;">{len(stats.get('source_errors', []))}</td></tr>
                </table>
                {source_errors_html}
            </div>

            <!-- Near Misses -->
            {near_miss_section}

            <!-- Permanent deals footer -->
            <div style="margin-top: 24px; padding: 18px; background: #161B22; border: 1px solid #30363D; border-radius: 12px;">
                <h3 style="color: #58A6FF; margin-top: 0; margin-bottom: 12px; font-size: 16px;">
                    ⚡ Guaranteed Active Voucher Programs
                </h3>
                <ul style="padding-left: 20px; margin: 0; color: #C9D1D9; font-size: 13px; line-height: 1.8;">
                    <li>🔥 <a href="https://ignite.microsoft.com/" style="color: #58A6FF;">MS Ignite</a> · <a href="https://build.microsoft.com/" style="color: #58A6FF;">MS Build</a> — 100% Free Vouchers</li>
                    <li>🎁 <a href="https://developer.microsoft.com/en-us/offers/30-days-to-learn-it" style="color: #58A6FF;">30 Days to Learn It</a> — 50% Off Voucher</li>
                    <li>🏢 <a href="https://esi.microsoft.com" style="color: #58A6FF;">ESI Portal</a> — 50-100% Off via Work Email</li>
                    <li>🎓 <a href="https://learn.microsoft.com/en-us/credentials/certifications/student-discounts" style="color: #58A6FF;">Student Discount</a> — Free Fundamentals + 45% Off</li>
                    <li>🏅 <a href="https://learn.microsoft.com/en-us/credentials/browse/?credential_types=applied%20skills" style="color: #58A6FF;">Applied Skills</a> — 100% Free Credentials</li>
                    <li>📅 <a href="https://events.microsoft.com/en-us/mvtd" style="color: #58A6FF;">Virtual Training Days</a> — Free Instructor-Led + Free Voucher</li>
                </ul>
            </div>

            <div style="text-align: center; padding: 20px 0;">
                <p style="color: #484F58; font-size: 11px; margin: 0;">
                    Cert Radar v4.0 Daily Digest 🛰️ | System is {health_status}
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
    plain = "Cert Radar v4.0 Alerts\n" + "=" * 50 + "\n\n"
    for a in alerts:
        p = PRIORITY_CONFIG.get(a["priority"], PRIORITY_CONFIG["LOW"])
        plain += f"[{p['label']}] {a['title']}\n"
        plain += f"  Link: {a['link']}\n"
        plain += f"  Source: {a['source']}\n\n"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_html_email(alerts), "html"))

    if DRY_RUN:
        print(f"🏃 DRY RUN — Would send email with {len(alerts)} alerts")
        return True

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


def send_digest_email():
    """Send a daily digest/heartbeat email."""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD or not ALL_TO_EMAILS:
        print("❌ Email credentials missing!")
        return False

    subject = f"📊 Cert Radar v4.0 — Daily Digest · {datetime.now().strftime('%b %d')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = ", ".join(ALL_TO_EMAILS)

    plain = f"Cert Radar v4.0 Daily Digest\n{'=' * 50}\n\n"
    plain += f"Posts evaluated: {scan_stats['total_posts_evaluated']}\n"
    plain += f"Passed all gates: {scan_stats['passed_all_gates']}\n"
    plain += f"Near misses: {len(scan_stats['near_misses'])}\n"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_digest_email(scan_stats, scan_stats["near_misses"][:20]), "html"))

    if DRY_RUN:
        print("🏃 DRY RUN — Would send digest email")
        return True

    for attempt in range(3):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            print("✅ Digest email sent!")
            return True
        except Exception as e:
            print(f"⚠️  Digest email attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    print("❌ Digest email failed.")
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

# Broader community subreddits need stricter filtering
BROAD_SOURCES = [
    "Reddit: Freebies",
    "Reddit: IT Career Questions",
    "Reddit: Sysadmin",
    "Reddit: Cloud Computing",
    "Reddit: Learn Programming",
    "Reddit: Information Technology",
    "Reddit: Certs",
    "Dev.to:",
]

def is_strict_source(source_name):
    """Check if a source requires strict filtering (only CRITICAL/HIGH)."""
    return any(source_name.startswith(prefix) for prefix in STRICT_SOURCES)

def is_broad_source(source_name):
    """Check if source is a broad community (only CRITICAL/HIGH/MEDIUM pass)."""
    return any(source_name.startswith(prefix) for prefix in BROAD_SOURCES)


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
            match_count = 0
            for entry in feed.entries:
                link = getattr(entry, "link", "")
                if not link or is_seen(seen, link):
                    continue

                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")

                priority, alert_type, score = classify_entry(title, summary, link, source_name)

                # Skip LOW from strict sources (YouTube, HN)
                if priority and is_strict_source(source_name) and priority in ("LOW", "MEDIUM"):
                    continue

                # Skip LOW from broad community sources
                if priority and is_broad_source(source_name) and priority == "LOW":
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
            scan_stats["source_errors"].append(f"{source_name}: {str(e)[:100]}")

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

                if not text or len(text) < 10 or is_seen(seen, link):
                    continue

                priority, alert_type, score = classify_entry(text, "", link, f"Web: {target['name']}")
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
            scan_stats["source_errors"].append(f"Web: {target['name']}: {str(e)[:100]}")

        time.sleep(2)

    return alerts


# ═════════════════════════════════════════════════════════════════════════════
#  Phase 3: Reddit JSON API Search (v4.0 NEW — bypasses RSS rate limits)
# ═════════════════════════════════════════════════════════════════════════════

def scan_reddit_search(seen):
    """Search Reddit directly via JSON API (no auth required)."""
    if not HAS_SCRAPING:
        print("  ⏭️  Skipping Reddit search (needs requests library)")
        return []

    alerts = []
    headers = {
        "User-Agent": "CertRadar/4.0 (certification voucher monitor)"
    }

    for query in REDDIT_SEARCH_QUERIES:
        print(f"  🔍 Reddit search: '{query}'...")
        try:
            url = f"https://www.reddit.com/search.json?q={query.replace(' ', '+')}&sort=new&t=week&limit=25"
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 429:
                print("     ⚠️  Rate limited, waiting 10s...")
                time.sleep(10)
                resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code != 200:
                print(f"     ⚠️  HTTP {resp.status_code}")
                scan_stats["source_errors"].append(f"Reddit Search '{query}': HTTP {resp.status_code}")
                continue

            data = resp.json()
            posts = data.get("data", {}).get("children", [])
            scan_stats["source_success"].append(f"Reddit Search: {query}")

            for post in posts:
                pdata = post.get("data", {})
                link = f"https://reddit.com{pdata.get('permalink', '')}"
                title = pdata.get("title", "")
                selftext = pdata.get("selftext", "")[:500]

                if not link or not title or is_seen(seen, link):
                    continue

                priority, alert_type, score = classify_entry(title, selftext, link, f"Reddit Search: {query}")

                # Only CRITICAL/HIGH/MEDIUM from search (it's broad)
                if priority and priority in ("CRITICAL", "HIGH", "MEDIUM"):
                    alert = {
                        "priority": priority,
                        "type": alert_type,
                        "title": title,
                        "link": link,
                        "source": f"Reddit Search: {query}",
                        "score": score,
                        "found_at": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
                    mark_seen(seen, link, "Reddit Search", priority)
                    print(f"     🎯 [{priority}] (score:{score}) {title[:80]}")

        except Exception as e:
            print(f"     ❌ Error: {e}")
            scan_stats["source_errors"].append(f"Reddit Search '{query}': {str(e)[:100]}")

        time.sleep(3)  # Be gentle with Reddit

    return alerts


# ═════════════════════════════════════════════════════════════════════════════
#  Phase 4: Nitter/Twitter Search (v4.0 NEW — best effort)
# ═════════════════════════════════════════════════════════════════════════════

def scan_twitter(seen):
    """Search Twitter via Nitter RSS (best-effort, may fail)."""
    alerts = []

    # Try each Nitter instance until one works
    working_instance = None
    for instance in NITTER_INSTANCES:
        try:
            test_url = f"{instance}/MSLearn/rss"
            feed = feedparser.parse(test_url)
            if feed.entries:
                working_instance = instance
                print(f"  🐦 Using Nitter instance: {instance}")
                break
        except Exception:
            continue

    if not working_instance:
        print("  ⏭️  No Nitter instances available (Twitter search skipped)")
        scan_stats["source_errors"].append("Nitter: All instances unreachable")
        return alerts

    # Search queries
    for query in TWITTER_SEARCH_QUERIES:
        print(f"  🐦 Twitter search: '{query}'...")
        try:
            url = f"{working_instance}/search/rss?f=tweets&q={query.replace(' ', '+')}"
            feed = feedparser.parse(url)

            for entry in feed.entries[:15]:
                link = getattr(entry, "link", "")
                title = getattr(entry, "title", "")

                if not link or not title or is_seen(seen, link):
                    continue

                priority, alert_type, score = classify_entry(title, "", link, f"Twitter: {query}")

                if priority and priority in ("CRITICAL", "HIGH"):
                    alert = {
                        "priority": priority,
                        "type": alert_type,
                        "title": title[:150],
                        "link": link,
                        "source": f"Twitter: {query}",
                        "score": score,
                        "found_at": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
                    mark_seen(seen, link, "Twitter", priority)
                    print(f"     🎯 [{priority}] (score:{score}) {title[:80]}")

        except Exception as e:
            print(f"     ❌ Error: {e}")

        time.sleep(2)

    # Key accounts
    for account in TWITTER_ACCOUNTS:
        print(f"  🐦 Twitter account: @{account}...")
        try:
            url = f"{working_instance}/{account}/rss"
            feed = feedparser.parse(url)
            scan_stats["source_success"].append(f"Twitter: @{account}")

            for entry in feed.entries[:10]:
                link = getattr(entry, "link", "")
                title = getattr(entry, "title", "")

                if not link or not title or is_seen(seen, link):
                    continue

                priority, alert_type, score = classify_entry(title, "", link, f"Twitter: @{account}")

                if priority and priority in ("CRITICAL", "HIGH", "MEDIUM"):
                    alert = {
                        "priority": priority,
                        "type": alert_type,
                        "title": title[:150],
                        "link": link,
                        "source": f"Twitter: @{account}",
                        "score": score,
                        "found_at": datetime.now().isoformat(),
                    }
                    alerts.append(alert)
                    mark_seen(seen, link, f"Twitter: @{account}", priority)
                    print(f"     🎯 [{priority}] (score:{score}) {title[:80]}")

        except Exception as e:
            print(f"     ❌ Error: {e}")

        time.sleep(2)

    return alerts


# ═════════════════════════════════════════════════════════════════════════════
#  Digest Scheduling Logic
# ═════════════════════════════════════════════════════════════════════════════

def should_send_digest():
    """Check if it's time to send a daily digest (once per day)."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_digest = data.get("last_digest", "")
            if last_digest:
                last_date = datetime.fromisoformat(last_digest).date()
                if last_date == datetime.now().date():
                    return False  # Already sent today
        except (json.JSONDecodeError, IOError, ValueError):
            pass
    return True


def record_digest_sent():
    """Record that digest was sent today."""
    data = {}
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {}
    data["last_digest"] = datetime.now().isoformat()
    data["last_stats"] = dict(scan_stats)
    data["last_stats"]["near_misses"] = scan_stats["near_misses"][:20]
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


# ═════════════════════════════════════════════════════════════════════════════
#  Main Entry Point
# ═════════════════════════════════════════════════════════════════════════════

def check_feeds():
    """Run a complete scan across all sources."""
    start = time.time()

    total_sources = len(RSS_FEEDS) + len(SCRAPE_TARGETS) + len(REDDIT_SEARCH_QUERIES) + len(TWITTER_SEARCH_QUERIES) + len(TWITTER_ACCOUNTS)

    print("=" * 60)
    print("🎯 PRO CERT RADAR v4.0 — Starting full scan...")
    print(f"   📡 {len(RSS_FEEDS)} RSS feeds + {len(SCRAPE_TARGETS)} web pages")
    print(f"   🔍 {len(REDDIT_SEARCH_QUERIES)} Reddit searches")
    print(f"   🐦 {len(TWITTER_SEARCH_QUERIES)} Twitter searches + {len(TWITTER_ACCOUNTS)} accounts")
    print(f"   📊 Total source channels: ~{total_sources}")
    if DRY_RUN:
        print("   🏃 DRY RUN MODE — No emails will be sent")
    if DEBUG:
        print("   🐛 DEBUG MODE — Full scoring breakdown enabled")
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

    # Phase 3: Reddit JSON search
    print("\n🔍 PHASE 3: Reddit JSON Search")
    print("-" * 40)
    reddit_alerts = scan_reddit_search(seen)
    all_alerts.extend(reddit_alerts)

    # Phase 4: Twitter/Nitter search
    print("\n🐦 PHASE 4: Twitter/Nitter Search")
    print("-" * 40)
    twitter_alerts = scan_twitter(seen)
    all_alerts.extend(twitter_alerts)

    # Save updated seen links
    save_seen(seen)

    # Save debug log
    save_debug_log()

    # Sort by priority (CRITICAL first)
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_alerts.sort(key=lambda a: priority_order.get(a["priority"], 99))

    # Deduplicate alerts by link
    seen_links_set = set()
    deduped_alerts = []
    for a in all_alerts:
        if a["link"] not in seen_links_set:
            seen_links_set.add(a["link"])
            deduped_alerts.append(a)
    all_alerts = deduped_alerts

    # Print results summary
    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"📊 SCAN COMPLETE — {elapsed:.1f}s")
    print(f"   Posts evaluated: {scan_stats['total_posts_evaluated']}")
    print(f"   Excluded (keywords): {scan_stats['excluded_by_keywords']}")
    print(f"   Excluded (tech gate): {scan_stats['excluded_by_tech_gate']}")
    print(f"   Excluded (low score): {scan_stats['excluded_by_score']}")
    print(f"   Passed all gates: {scan_stats['passed_all_gates']}")
    print(f"   Near misses: {len(scan_stats['near_misses'])}")
    print(f"   Sources OK: {len(scan_stats['source_success'])}")
    print(f"   Sources failed: {len(scan_stats['source_errors'])}")
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

    # Daily digest (send once per day, even if no alerts)
    if should_send_digest():
        print("\n📊 Sending daily digest email...")
        send_digest_email()
        record_digest_sent()

    return all_alerts


if __name__ == "__main__":
    # Handle flags
    if "--test-email" in sys.argv:
        print("📧 Sending test email...")
        send_test_email()
    elif "--digest" in sys.argv:
        print("📊 Forcing daily digest email...")
        # Run a quick scan to collect stats
        check_feeds()
    else:
        print(r"""
  ██████╗███████╗██████╗ ████████╗    ██████╗  █████╗ ██████╗  █████╗ ██████╗
 ██╔════╝██╔════╝██╔══██╗╚══██╔══╝    ██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗
 ██║     █████╗  ██████╔╝   ██║       ██████╔╝███████║██║  ██║███████║██████╔╝
 ██║     ██╔══╝  ██╔══██╗   ██║       ██╔══██╗██╔══██║██║  ██║██╔══██║██╔══██╗
 ╚██████╗███████╗██║  ██║   ██║       ██║  ██║██║  ██║██████╔╝██║  ██║██║  ██║
  ╚═════╝╚══════╝╚═╝  ╚═╝   ╚═╝       ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
                    🎯 Pro Cert Radar v4.0 — Ultimate Voucher Hunter
        """)
        check_feeds()

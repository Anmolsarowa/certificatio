import feedparser
import requests
import os

INSTANT_KEYWORDS = ["free voucher", "free exam", "free certification", "coupon code", "claim your"]
EVENT_KEYWORDS = ["attend", "register", "virtual training", "webinar", "event", "ignite", "ai tour", "bootcamp"]

FEEDS = [
    "https://www.reddit.com/r/MicrosoftCertifications/.rss",
    "https://www.reddit.com/r/AzureCertification/.rss",
    "https://www.reddit.com/r/PowerPlatform/.rss",
    "https://www.reddit.com/r/dynamics365/.rss",
    "https://techcommunity.microsoft.com/t5/custom/page/page-id/activity.rss"
]

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def get_seen_links():
    if not os.path.exists("seen_links.txt"):
        return set()
    with open("seen_links.txt", "r") as file:
        return set(line.strip() for line in file)

def save_seen_link(link):
    with open("seen_links.txt", "a") as file:
        file.write(f"{link}\n")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload)
        print("Alert sent!")
    except Exception as e:
        print(f"Failed: {e}")

def check_feeds():
    seen_links = get_seen_links()
    found_new = False
    
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title.lower()
            summary = entry.summary.lower()
            link = entry.link
            
            if link in seen_links:
                continue
                
            message = None
            
            if any(keyword in title or keyword in summary for keyword in EVENT_KEYWORDS) and ("voucher" in summary or "certification" in summary or "exam" in summary):
                message = f"📅 EVENT ALERT: ATTEND TO GET VOUCHER! 📅\n\n{entry.title}\n\n⚠️ You must register and attend this event!\n\nLink: {entry.link}"
                
            elif any(keyword in title or keyword in summary for keyword in INSTANT_KEYWORDS):
                message = f"🚨 INSTANT FREE CERT ALERT! 🚨\n\n{entry.title}\n\nLink: {entry.link}"
            
            if message:
                send_telegram_message(message)
                save_seen_link(link)
                found_new = True
                
    if not found_new:
        print("Checked. No new events or coupons found.")

if __name__ == "__main__":
    print("Pro Event Radar Checking...")
    check_feeds()

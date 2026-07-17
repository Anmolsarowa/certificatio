import feedparser
import smtplib
from email.mime.text import MIMEText
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

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL_ADDRESS")

def get_seen_links():
    if not os.path.exists("seen_links.txt"):
        return set()
    with open("seen_links.txt", "r") as file:
        return set(line.strip() for line in file)

def save_seen_link(link):
    with open("seen_links.txt", "a") as file:
        file.write(f"{link}\n")

def send_email_alert(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_EMAIL
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email Alert sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")

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
                
            subject = None
            body = None
            
            if any(keyword in title or keyword in summary for keyword in EVENT_KEYWORDS) and ("voucher" in summary or "certification" in summary or "exam" in summary):
                subject = "📅 EVENT ALERT: Attend to get Voucher!"
                body = f"⚠️ You must register and attend this event!\n\nTitle: {entry.title}\n\nLink: {entry.link}"
                
            elif any(keyword in title or keyword in summary for keyword in INSTANT_KEYWORDS):
                subject = "🚨 INSTANT FREE CERT ALERT!"
                body = f"Link: {entry.link}\n\nTitle: {entry.title}"
            
            if subject:
                send_email_alert(subject, body)
                save_seen_link(link)
                found_new = True
                
    if not found_new:
        print("Checked. No new events or coupons found.")

if __name__ == "__main__":
    print("Pro Event Radar Checking...")
    check_feeds()
    send_email_alert("Test Email", "Your Cert Radar is working perfectly!")

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import html
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Ensure utf-8 encoding for console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
SEEN_FILE = os.path.join(SCRIPT_DIR, "seen_requests.json")

# Simple HTTP handler for Render keep-alive and health check
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Khamsat Alert Bot is Running 24/7!\n".encode("utf-8"))

    def log_message(self, format, *args):
        # Silence access logs to keep terminal clean
        return

def run_health_server(port):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"[✓] تم تشغيل خادم المراقبة على المنفذ {port}")
        server.serve_forever()
    except Exception as e:
        print(f"[-] خطأ في تشغيل خادم المراقبة: {e}")

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    return cfg

def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_ids(seen_ids):
    trimmed = list(seen_ids)[-300:]
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f)
    except Exception as e:
        print(f"[-] Error saving seen IDs: {e}")

def send_telegram_message(token, chat_id, message_html):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return False, f"HTTP {e.code}: {err_msg}"
    except Exception as e:
        return False, str(e)

def fetch_requests():
    url = "https://khamsat.com/community/requests"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        page_html = resp.read().decode("utf-8")

    blocks = re.findall(r'<td class="details-td">(.*?)</td>', page_html, re.DOTALL)
    items = []
    for b in blocks:
        title_match = re.search(r'<h3 class="details-head"><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h3>', b)
        if not title_match:
            continue
        href = title_match.group(1)
        title = html.unescape(title_match.group(2).strip())
        
        user_match = re.search(r'<a class="user"[^>]*>(.*?)</a>', b)
        user_name = "مستخدم"
        if user_match:
            clean_user = re.sub(r'<[^>]+>', '', user_match.group(1)).strip()
            if clean_user:
                user_name = html.unescape(clean_user)

        time_match = re.search(r'<span[^>]*dir="ltr"[^>]*>(.*?)</span>', b, re.DOTALL)
        post_time = "منذ لحظات"
        if time_match:
            post_time = " ".join(time_match.group(1).split())
            post_time = html.unescape(post_time)

        id_match = re.search(r'/requests/(\d+)', href)
        post_id = int(id_match.group(1)) if id_match else 0

        full_link = f"https://khamsat.com{href}"
        items.append({
            "id": post_id,
            "title": title,
            "user": user_name,
            "time": post_time,
            "url": full_link
        })
    return items

def matches_keywords(title, keywords):
    if not keywords:
        return True
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in keywords)

def main():
    config = load_config()
    token = os.environ.get("BOT_TOKEN") or config.get("bot_token", "").strip()
    chat_id = os.environ.get("CHAT_ID") or config.get("chat_id", "").strip()
    interval = int(os.environ.get("CHECK_INTERVAL") or config.get("check_interval_seconds", 30))
    
    # Keywords from env (comma separated) or config
    env_kw = os.environ.get("KEYWORDS")
    if env_kw:
        keywords = [k.strip() for k in env_kw.split(",") if k.strip()]
    else:
        keywords = config.get("keywords", [])

    if not token or not chat_id:
        print("[-] خطأ: لم يتم العثور على BOT_TOKEN أو CHAT_ID في config.json أو متغيرات البيئة.")
        sys.exit(1)

    # Start lightweight web server for Render / Cloud port binding & keep-alive
    port = int(os.environ.get("PORT", 10000))
    t = threading.Thread(target=run_health_server, args=(port,), daemon=True)
    t.start()

    print("=" * 60)
    print("🚀 تم تشغيل بوت رادار طلبات خمسات (Khamsat Alert Bot)")
    print(f"⏱️ معدل الفحص: كل {interval} ثانية")
    if keywords:
        print(f"🔍 فلترة الكلمات المفتاحية: {', '.join(keywords)}")
    else:
        print("🔔 يتم مراقبة جميع الطلبات بدون فلترة")
    print("=" * 60)

    seen_ids = load_seen_ids()

    # Initial scan
    print("[*] جاري فحص الصفحة الحالية لأول مرة...")
    try:
        current_items = fetch_requests()
        for item in current_items:
            seen_ids.add(item["id"])
        save_seen_ids(seen_ids)
        print(f"[✓] تم حفظ {len(current_items)} طلب قديم لتجنب الإزعاج بالطلبات السابقة.")
    except Exception as e:
        print(f"[-] خطأ أثناء الفحص الأولي: {e}")

    # Send startup message to user
    startup_msg = (
        "🚀 <b>تم تشغيل رادار طلبات خمسات بنجاح في السحاب!</b>\n\n"
        f"⏱️ <b>معدل الفحص:</b> كل {interval} ثانية\n"
        + (f"🔍 <b>الفلترة مفعلة على:</b> {', '.join(keywords)}\n" if keywords else "🔔 <b>الفلترة:</b> مراقبة كل الطلبات الجديدة\n")
        + "\n<i>البوت سيعمل الآن 24/7 دون الحاجة لتشغيل الكمبيوتر!</i> ⚡"
    )
    ok, resp = send_telegram_message(token, chat_id, startup_msg)
    if ok:
        print("[✓] تم إرسال رسالة تفعيل للبوت على تليجرام بنجاح!")
    else:
        print(f"[!] تنبيه: تعذر إرسال رسالة التفعيل: {resp}")

    # Main monitoring loop
    print("\n[*] جاري بدء المراقبة المستمرة...")
    while True:
        try:
            time.sleep(interval)
            items = fetch_requests()
            now_str = datetime.now().strftime("%H:%M:%S")

            new_items = [it for it in items if it["id"] not in seen_ids]

            if new_items:
                print(f"[{now_str}] 🎯 تم اكتشاف {len(new_items)} طلب جديد!")
                for it in reversed(new_items):
                    seen_ids.add(it["id"])
                    if matches_keywords(it["title"], keywords):
                        alert_msg = (
                            "🚨 <b>طلب جديد في خمسات!</b>\n\n"
                            f"📌 <b>العنوان:</b> {html.escape(it['title'])}\n"
                            f"👤 <b>الناشر:</b> {html.escape(it['user'])}\n"
                            f"⏱️ <b>الوقت:</b> {html.escape(it['time'])}\n\n"
                            f"👉 <a href=\"{it['url']}\">اضغط هنا لفتح الطلب والتقديم فوراً 🚀</a>"
                        )
                        s_ok, s_err = send_telegram_message(token, chat_id, alert_msg)
                        if s_ok:
                            print(f"    [✓] تم الإرسال: {it['title'][:40]}...")
                        else:
                            print(f"    [-] فشل إرسال الإشعار للطلب {it['id']}: {s_err}")
                    else:
                        print(f"    [i] تم تخطي الطلب (لا يطابق الكلمات المفتاحية): {it['title'][:40]}")
                
                save_seen_ids(seen_ids)
            else:
                print(f"[{now_str}] لا توجد طلبات جديدة. الفحص القادم بعد {interval} ثانية...")

        except KeyboardInterrupt:
            print("\n[!] تم إيقاف البوت بواسطة المستخدم.")
            break
        except Exception as e:
            now_str = datetime.now().strftime("%H:%M:%S")
            print(f"[{now_str}] حدث خطأ مؤقت: {e}. جاري إعادة المحاولة...")

if __name__ == "__main__":
    main()

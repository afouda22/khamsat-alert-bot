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

# Prevent Windows console from freezing on mouse click (Disable QuickEdit Mode)
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        hStdIn = kernel32.GetStdHandle(-10)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(hStdIn, ctypes.byref(mode))
        ENABLE_QUICK_EDIT_MODE = 0x0040
        kernel32.SetConsoleMode(hStdIn, mode.value & ~ENABLE_QUICK_EDIT_MODE)
    except Exception:
        pass

# Prevent Windows from entering Sleep automatically while the bot is running
if sys.platform == "win32":
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
STATE_FILE = os.path.join(SCRIPT_DIR, "bot_state.json")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Khamsat Alert Bot is Running 24/7!\n".encode("utf-8"))

    def log_message(self, format, *args):
        return

def run_health_server(port):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()
    except Exception:
        pass

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    return cfg

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("max_id", 0), set(data.get("seen_ids", []))
        except Exception:
            pass
    return 0, set()

def save_state(max_id, seen_ids):
    trimmed = list(seen_ids)[-300:]
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"max_id": max_id, "seen_ids": trimmed}, f)
    except Exception as e:
        print(f"[-] Error saving state: {e}")

def send_telegram_message(token, chat_id, message_html):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
        "disable_notification": False
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return False, f"HTTP {e.code}: {err_msg}"
    except Exception as e:
        return False, str(e)

def fetch_requests():
    url = "https://khamsat.com/community/requests"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cache-Control": "no-cache"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
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

        full_link = f"https://khamsat.com{href}#add_comment"
        items.append({
            "id": post_id,
            "title": title,
            "user": user_name,
            "time": post_time,
            "url": full_link
        })
    return items

def is_old_time(time_str):
    old_indicators = ["يوم", "ايام", "أيام", "شهر", "أشهر", "اسبوع", "أسبوع"]
    return any(ind in time_str for ind in old_indicators)

def matches_keywords(title, keywords):
    if not keywords:
        return True
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in keywords)

def dispatch_alert(token, chat_id, it):
    alert_msg = (
        "⚡ <b>طلب جديد في خمسات! (فرصة أول عرض)</b>\n\n"
        f"📌 <b>العنوان:</b> {html.escape(it['title'])}\n"
        f"👤 <b>الناشر:</b> {html.escape(it['user'])}\n"
        f"⏱️ <b>الوقت:</b> {html.escape(it['time'])}\n\n"
        f"🚀 <a href=\"{it['url']}\">اضغط هنا لفتح صندوق تقديم العرض مباشرة!</a>"
    )
    s_ok, s_err = send_telegram_message(token, chat_id, alert_msg)
    if s_ok:
        print(f"\n[⚡ SENT TO TELEGRAM] {it['title']} (#{it['id']})")
    else:
        print(f"\n[-] Failed to send alert for #{it['id']}: {s_err}")
    return s_ok

def main():
    config = load_config()
    token = os.environ.get("BOT_TOKEN") or config.get("bot_token", "").strip()
    chat_id = os.environ.get("CHAT_ID") or config.get("chat_id", "").strip()
    interval = int(os.environ.get("CHECK_INTERVAL") or config.get("check_interval_seconds", 10))
    
    env_kw = os.environ.get("KEYWORDS")
    if env_kw:
        keywords = [k.strip() for k in env_kw.split(",") if k.strip()]
    else:
        keywords = config.get("keywords", [])

    if not token or not chat_id:
        print("[-] Error: BOT_TOKEN or CHAT_ID missing.")
        sys.exit(1)

    port = int(os.environ.get("PORT", 10000))
    t = threading.Thread(target=run_health_server, args=(port,), daemon=True)
    t.start()

    print("=" * 60)
    print(">> KHAMSAT RADAR BOT - ACTIVE & SCANNING")
    print(f">> Interval: Every {interval} seconds")
    print(">> Sleep Prevention: ENABLED (PC will stay awake)")
    print(">> QuickEdit Freezing: DISABLED (Clicks won't pause bot)")
    if keywords:
        print(f">> Keywords filter: {', '.join(keywords)}")
    else:
        print(">> Monitoring: ALL new requests")
    print("=" * 60)

    max_seen_id, seen_ids = load_state()

    try:
        current_items = fetch_requests()
        if max_seen_id == 0:
            for item in current_items:
                seen_ids.add(item["id"])
                if item["id"] > max_seen_id:
                    max_seen_id = item["id"]
            save_state(max_seen_id, seen_ids)
            print(f"[✓] Initialized baseline at #{max_seen_id}")
        else:
            catch_up_items = [
                it for it in current_items
                if it["id"] > max_seen_id and it["id"] not in seen_ids and not is_old_time(it["time"])
            ]
            if catch_up_items:
                print(f"[🎯] Found {len(catch_up_items)} missed new request(s)! Sending to Telegram...")
                catch_up_items.sort(key=lambda x: x["id"])
                for it in catch_up_items:
                    seen_ids.add(it["id"])
                    if it["id"] > max_seen_id:
                        max_seen_id = it["id"]
                    if matches_keywords(it["title"], keywords):
                        dispatch_alert(token, chat_id, it)
                save_state(max_seen_id, seen_ids)
            else:
                for it in current_items:
                    seen_ids.add(it["id"])
                save_state(max_seen_id, seen_ids)

    except Exception as e:
        print(f"[-] Init error: {e}")

    print("\n[*] Live monitoring started. Awaiting new requests...")
    scan_count = 0
    while True:
        try:
            time.sleep(interval)
            items = fetch_requests()
            scan_count += 1
            now_str = datetime.now().strftime("%H:%M:%S")

            new_genuine_items = []
            for it in items:
                if it["id"] not in seen_ids:
                    seen_ids.add(it["id"])
                    if it["id"] > max_seen_id and not is_old_time(it["time"]):
                        new_genuine_items.append(it)

            if new_genuine_items:
                new_genuine_items.sort(key=lambda x: x["id"])
                for it in new_genuine_items:
                    if it["id"] > max_seen_id:
                        max_seen_id = it["id"]

                    if matches_keywords(it["title"], keywords):
                        dispatch_alert(token, chat_id, it)
                
                save_state(max_seen_id, seen_ids)
            else:
                # Live dynamic counter on the same line so the user sees it's actively ticking!
                sys.stdout.write(f"\r[STATUS: RUNNING] Last scan: {now_str} | Scans: {scan_count} | Monitoring Khamsat...")
                sys.stdout.flush()

        except KeyboardInterrupt:
            print("\n[!] Bot stopped by user.")
            break
        except Exception as e:
            now_str = datetime.now().strftime("%H:%M:%S")
            sys.stdout.write(f"\r[RETRY: {now_str}] Network notice: {e}. Retrying in {interval}s...")
            sys.stdout.flush()

if __name__ == "__main__":
    main()

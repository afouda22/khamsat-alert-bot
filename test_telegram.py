import json
import os
import sys
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

token = config["bot_token"]
chat_id = config["chat_id"]

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": "👋 <b>أهلاً بك!</b> تم اختبار الاتصال بالبوت بنجاح 🚀\nالبوت جاهز للعمل ومراقبة طلبات خمسات.",
    "parse_mode": "HTML"
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("[✓] تم إرسال الرسالة التجريبية بنجاح! شيك على تليجرام.")
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8")
    print(f"[-] خطأ من تليجرام ({e.code}): {err}")
    if "chat not found" in err:
        print("💡 الحل: ادخل على رابط البوت https://t.me/khamsat_myalert_bot واضغط على زر Start أولاً!")
except Exception as e:
    print(f"[-] خطأ في الاتصال: {e}")

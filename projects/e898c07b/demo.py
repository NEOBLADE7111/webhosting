import os
import sqlite3
import requests
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ================== CONFIGURATION ==================
BOT_TOKEN = "8274427241:AAGWZrx5GJCVt43FjmIgzf_OFlPtMZINMbQ"  # Replace with your bot token
ADMIN_ID = [7830287371]  # Add your Telegram ID here
CHANNEL_USERNAME = "@darknyteexodus"  # Must join channel

# ================== API CONFIGURATION ==================
API_URL = "https://normal-num-info.vercel.app/info"  # <-- YOUR API
# Format: https://normal-num-info.vercel.app/info?number=PHONE_NUMBER

# Footer for every message
FOOTER = "\n───────────────\nMade by @darknyteexodus\nDeveloper @d4RKNYTEADMIN"

# ================== DATABASE SETUP ==================
def init_database():
    """Auto-create database and tables if not exists"""
    conn = sqlite3.connect('exodus_osint.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    
    # Channels table (for admin panel)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            channel_name TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Requests log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone_number TEXT,
            api_response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add default admin if not exists
    cursor.execute('INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, 1)', (ADMIN_ID[0],))
    
    # Insert default channel
    cursor.execute('''
        INSERT OR IGNORE INTO channels (channel_id, channel_name, added_by)
        VALUES (?, ?, ?)
    ''', (CHANNEL_USERNAME, "Darknyte Exodus", ADMIN_ID[0]))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# Initialize database on startup
init_database()

# ================== HELPER FUNCTIONS ==================
def get_db_connection():
    """Get database connection"""
    return sqlite3.connect('exodus_osint.db', check_same_thread=False)

def is_admin(user_id):
    """Check if user is admin"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def is_banned(user_id):
    """Check if user is banned"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def add_user(user_id, username, first_name, last_name):
    """Add user to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, last_name, joined_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, datetime.now()))
    conn.commit()
    conn.close()

def log_request(user_id, phone_number, api_response):
    """Log API request to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO requests (user_id, phone_number, api_response)
        VALUES (?, ?, ?)
    ''', (user_id, phone_number, api_response))
    conn.commit()
    conn.close()

# ================== API CALL FUNCTION ==================
def call_number_api(phone_number):
    """
    DIRECT API CALL TO YOUR ENDPOINT
    https://normal-num-info.vercel.app/info?number=PHONE_NUMBER
    """
    try:
        # Clean phone number
        phone_number = phone_number.strip()
        
        # API call to your endpoint
        api_endpoint = f"{API_URL}?number={phone_number}"
        print(f"🔗 Calling API: {api_endpoint}")
        
        # Make GET request to your API
        response = requests.get(api_endpoint, timeout=30)
        
        # Check if request was successful
        if response.status_code == 200:
            # Try to parse as JSON
            try:
                api_data = response.json()
                
                # Format the response nicely
                formatted_response = format_api_response(api_data, phone_number)
                return formatted_response
                
            except json.JSONDecodeError:
                # If not JSON, return raw text
                raw_text = response.text[:4000]  # Telegram limit
                return format_raw_response(raw_text, phone_number)
        
        else:
            error_msg = f"""
❌ **API Error**

**Status Code:** {response.status_code}
**Number:** {phone_number}
**API:** {API_URL}

**Possible Issues:**
1. API Server Down
2. Invalid Number Format
3. API Rate Limit

**Response:** {response.text[:500] if response.text else 'No response'}
{FOOTER}
            """
            return error_msg
            
    except requests.exceptions.Timeout:
        return f"⏳ **API Timeout Error**\n\nAPI took too long to respond for number: {phone_number}\n\nPlease try again later.{FOOTER}"
    
    except requests.exceptions.ConnectionError:
        return f"🔌 **Connection Error**\n\nCannot connect to API server.\n\nNumber: {phone_number}\nAPI: {API_URL}\n\nCheck your internet connection.{FOOTER}"
    
    except Exception as e:
        return f"⚠️ **Unexpected Error**\n\nError: {str(e)}\n\nNumber: {phone_number}\n\nContact admin if issue persists.{FOOTER}"

def format_api_response(api_data, phone_number):
    """Format JSON API response for Telegram"""
    try:
        # Check if API returned valid data
        if isinstance(api_data, dict):
            # Start building response
            response_text = f"📱 **Number Information**\n\n"
            response_text += f"**📞 Number:** `{phone_number}`\n"
            
            # Add all data from API
            for key, value in api_data.items():
                if value and str(value).strip():
                    # Format key nicely
                    pretty_key = key.replace('_', ' ').title()
                    response_text += f"**{pretty_key}:** {value}\n"
            
            # Add footer
            response_text += f"\n🔗 **Source:** {API_URL}\n"
            response_text += f"📊 **Data from API**\n{FOOTER}"
            
            return response_text
        
        elif isinstance(api_data, str):
            return f"📱 **API Response**\n\nNumber: {phone_number}\n\n{api_data}\n\n{FOOTER}"
        
        else:
            return f"📱 **Number Lookup**\n\n**Number:** {phone_number}\n\n**API Response:** {str(api_data)[:3000]}\n\n{FOOTER}"
    
    except Exception as e:
        return f"📱 **Raw API Data**\n\nNumber: {phone_number}\n\n{json.dumps(api_data, indent=2)[:3500]}\n\n{FOOTER}"

def format_raw_response(raw_text, phone_number):
    """Format raw text response"""
    return f"📱 **Number Information**\n\n**Number:** {phone_number}\n\n**API Response:**\n{raw_text}\n\n{FOOTER}"

def check_channel_membership(user_id):
    """Check if user joined channel - PLACEHOLDER"""
    # You need to implement actual Telegram channel check
    # This requires bot to be admin in channel
    return True  # Temporary - implement actual check

# ================== COMMAND HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    
    # Check if user joined channel
    if not check_channel_membership(user.id):
        keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ **Please join our channel first!**\n\n"
            f"You must join: {CHANNEL_USERNAME}\n"
            f"Then try /start again.{FOOTER}",
            reply_markup=reply_markup
        )
        return
    
    # Add user to database
    add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_msg = (
        f"🤖 **Welcome to Exodus OSINT Bot**\n\n"
        f"**API Integrated:** ✅\n"
        f"**API Endpoint:** `{API_URL}`\n\n"
        f"**Commands:**\n"
        f"• /start - Start bot\n"
        f"• /info <number> - Get number info\n"
        f"• /admin - Admin panel\n"
        f"• /help - Show help\n\n"
        f"**Example:**\n"
        f"`/info 6395954711`\n"
        f"`/info 917738828272`\n\n"
        f"**Note:** Direct API response shown{FOOTER}"
    )
    
    await update.message.reply_text(welcome_msg)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Number information lookup - DIRECT FROM YOUR API"""
    user = update.effective_user
    
    # Check if banned
    if is_banned(user.id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    
    # Check channel membership
    if not check_channel_membership(user.id):
        keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ **Please join our channel first!**\n\n"
            f"Join: {CHANNEL_USERNAME}\n"
            f"Then try again.{FOOTER}",
            reply_markup=reply_markup
        )
        return
    
    # Check if user provided number
    if not context.args:
        await update.message.reply_text(
            f"❌ **Please provide a phone number!**\n\n"
            f"**Usage:**\n"
            f"`/info 6395954711`\n"
            f"`/info 911234567890`\n\n"
            f"**Your API:** {API_URL}\n{FOOTER}"
        )
        return
    
    phone_number = context.args[0].strip()
    
    # Validate number format
    if not phone_number.isdigit() or len(phone_number) < 10:
        await update.message.reply_text(
            f"❌ **Invalid Number Format**\n\n"
            f"Please provide a valid phone number.\n"
            f"Example: `6395954711` or `916395954711`\n\n"
            f"**Your input:** {phone_number}{FOOTER}"
        )
        return
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        f"🔍 **Calling Your API...**\n\n"
        f"**Number:** `{phone_number}`\n"
        f"**API:** `{API_URL}`\n\n"
        f"⏳ Please wait...{FOOTER}"
    )
    
    try:
        # ================================
        # DIRECT API CALL - YOUR ENDPOINT
        # ================================
        api_response = call_number_api(phone_number)
        
        # Log the request
        log_request(user.id, phone_number, api_response[:1000])
        
        # Send API response to user (NO MODIFICATION)
        await processing_msg.edit_text(api_response)
        
        print(f"✅ Request processed for {user.id}: {phone_number}")
        
    except Exception as e:
        error_msg = f"""
⚠️ **Bot Error**

**Number:** {phone_number}
**Error:** {str(e)}

**API Endpoint:** {API_URL}

Please try again or contact admin.
{FOOTER}
        """
        await processing_msg.edit_text(error_msg)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin Panel"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📜 API Logs", callback_data="admin_logs")],
        [InlineKeyboardButton("⚙️ Advanced", callback_data="admin_advanced")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔧 **Exodus OSINT Admin Panel**\n\n"
        f"**API Status:** ✅ Connected\n"
        f"**API URL:** {API_URL}\n\n"
        f"Select an option below:{FOOTER}",
        reply_markup=reply_markup
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Unauthorized!")
        return
    
    data = query.data
    
    if data == "admin_stats":
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get stats
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        banned_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM requests")
        total_requests = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT phone_number) FROM requests")
        unique_numbers = cursor.fetchone()[0]
        
        conn.close()
        
        stats_msg = (
            f"📊 **Bot Statistics**\n\n"
            f"**👥 Total Users:** {total_users}\n"
            f"**🚫 Banned Users:** {banned_users}\n"
            f"**📞 API Requests:** {total_requests}\n"
            f"**🔢 Unique Numbers:** {unique_numbers}\n"
            f"**🔗 API Endpoint:** {API_URL}\n\n"
            f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*{FOOTER}"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_msg, reply_markup=reply_markup)
    
    elif data == "admin_logs":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT phone_number, timestamp FROM requests ORDER BY id DESC LIMIT 20")
        logs = cursor.fetchall()
        conn.close()
        
        logs_list = "📜 **Recent API Requests (Last 20)**\n\n"
        for log in logs:
            number, time = log
            logs_list += f"• `{number}` - {time}\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"{logs_list}\n**Total Requests:** {len(logs)}{FOOTER}",
            reply_markup=reply_markup
        )
    
    elif data == "admin_back":
        await admin_panel(update, context)
    
    elif data == "admin_users":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, joined_at FROM users ORDER BY joined_at DESC LIMIT 30")
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            await query.edit_message_text("No users found.")
            return
        
        users_list = "👥 **Recent Users (Last 30)**\n\n"
        for user in users:
            uid, username, joined = user
            users_list += f"• `{uid}` - @{username or 'NoUsername'} - {joined[:10]}\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"{users_list}\n**Total shown:** {len(users)}{FOOTER}",
            reply_markup=reply_markup
        )
    
    else:
        await query.edit_message_text(f"Feature coming soon!\n\n{FOOTER}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = (
        f"🆘 **Exodus OSINT Bot Help**\n\n"
        f"**API Integrated:** ✅\n"
        f"**Endpoint:** `{API_URL}`\n\n"
        f"**Commands:**\n"
        f"/start - Start bot\n"
        f"/info <number> - Get number info (Direct API response)\n"
        f"/admin - Admin panel\n"
        f"/help - Show this help\n\n"
        f"**Examples:**\n"
        f"• `/info 6395954711`\n"
        f"• `/info 919876543210`\n\n"
        f"**How it works:**\n"
        f"1. You send number\n"
        f"2. Bot calls API\n"
        f"3. API response sent directly to you\n\n"
        f"**Channel:** {CHANNEL_USERNAME}{FOOTER}"
    )
    
    await update.message.reply_text(help_text)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users (Admin only)"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not context.args:
        await update.message.reply_text(
            f"**Usage:**\n"
            f"/broadcast Your message here\n\n"
            f"**Example:**\n"
            f"/broadcast Bot update coming soon!{FOOTER}"
        )
        return
    
    message = " ".join(context.args)
    full_message = f"📢 **Admin Broadcast**\n\n{message}\n\n{FOOTER}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = cursor.fetchall()
    conn.close()
    
    sent_count = 0
    failed_count = 0
    
    processing = await update.message.reply_text(f"📤 Broadcasting to {len(users)} users...")
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=full_message)
            sent_count += 1
        except:
            failed_count += 1
    
    await processing.edit_text(
        f"✅ **Broadcast Complete**\n\n"
        f"✅ Sent: {sent_count}\n"
        f"❌ Failed: {failed_count}\n"
        f"📊 Total: {len(users)}\n\n"
        f"Message: {message[:50]}...{FOOTER}"
    )

# ================== MAIN FUNCTION ==================
def main():
    """Start the bot"""
    print("🚀 Starting Exodus OSINT Bot...")
    print(f"📞 API Endpoint: {API_URL}")
    print(f"📢 Channel: {CHANNEL_USERNAME}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast))
    
    # Callback handler for admin panel
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    
    # Start bot
    print("✅ Bot is running...")
    print("📱 Send /info 6395954711 to test API")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
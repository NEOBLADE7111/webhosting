# Configuration
from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
import os
import uuid
import secrets
import shutil
import time
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from typing import Union
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database
import manager
import editor
# Removed sys.stdout wrapper to avoid buffering issuesd

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
NGROK_AUTH = os.getenv("NGROK_AUTH")
WEB_URL = os.getenv("WEB_URL") or "http://localhost:8000"

# Configuration startup...

# Startup configuration for Railway
WEB_URL = os.getenv("WEB_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN") or "http://localhost:8000"
if WEB_URL and not WEB_URL.startswith("http"):
    WEB_URL = f"https://{WEB_URL}"

# Railway automatically sets PORT
PORT = int(os.getenv("PORT", 8000))
print(f"🚀 Railway Deployment Active: {WEB_URL} on PORT {PORT}", flush=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

user_states = {}

def get_premium_header(title):
    return f"─── ⋆⋅☆⋅⋆ ───\n<b>{title}</b>\n─────────────"

def get_main_keyboard():
    kb = [
        [KeyboardButton(text="📊 MY ACCOUNT"), KeyboardButton(text="💰 WALLET")],
        [KeyboardButton(text="💎 UPGRADE"), KeyboardButton(text="📁 MY PROJECTS")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def main_menu(user_id):
    user = database.get_user(user_id)
    if not user: return None, "Error loading account."
    
    if database.is_maintenance() and user_id != ADMIN_ID:
        return None, "🚧 <b>System Maintenance</b>\n\nBot is currently undergoing upgrades. Please check back later!"

    if user.get('is_banned'):
        return None, "🚫 <b>ACCESS DENIED</b>\n\nYou have been banned from using this service."

    slots = user['slots']
    projects = database.get_user_projects(user_id)
    active = len([p for p in projects if p['status'] == 'running'])
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚀 UPLOAD", callback_data="btn_upload"),
        InlineKeyboardButton(text="🐙 CLONE", callback_data="btn_clone")
    )
    builder.row(
        InlineKeyboardButton(text="📁 MY PROJECTS", callback_data="btn_projects"),
        InlineKeyboardButton(text="🖥 WEB ACCESS", callback_data="btn_web")
    )
    builder.row(
        InlineKeyboardButton(text="🤝 INVITE", callback_data="btn_referral"),
        InlineKeyboardButton(text="📖 HOW TO USE", callback_data="btn_help")
    )
    builder.row(InlineKeyboardButton(text="📞 SUPPORT", url="https://t.me/Rytce"))
    
    if user_id == ADMIN_ID:
        builder.row(InlineKeyboardButton(text="🛡 ADMIN PANEL", callback_data="btn_admin"))
    
    text = (
        f"{get_premium_header('GOD-LEVEL HOSTING')}\n\n"
        f"👤 <b>Welcome:</b> <code>{user['username'] or user_id}</code>\n"
        f"⭐ <b>Plan:</b> <code>{user.get('plan', 'FREE')}</code>\n"
        f"📦 <b>Usage:</b> <code>{active}/{slots} Slots used</code>\n"
        f"🌐 <b>Web:</b> <a href='{WEB_URL}'>Open Browser Console</a>\n\n"
        f"<i>Status: System Operational ✅</i>"
    )
    return builder.as_markup(), text

async def check_fsub(user_id):
    """Returns a list of channels the user hasn't joined."""
    # Admin skips fsub
    if user_id == ADMIN_ID:
        return []

    not_joined = []
    force_channels = database.get_force_channels()
    for ch in force_channels:
        try:
            member = await bot.get_chat_member(ch['channel_id'], user_id)
            print(f"DEBUG: Fsub Check {ch['channel_id']} for {user_id} -> Status: {member.status}")
            if member.status in ["left", "kicked"]:
                not_joined.append(ch)
        except Exception as e:
            # If bot not admin or ID invalid, skip but log
            print(f"Fsub Check Error for {ch['channel_id']}: {e}")
            # Optional: If bot can't check, should we block? Currently we skip (allow).
            # To be strict: not_joined.append(ch) 
            pass
    return not_joined

async def show_fsub_shield(message_or_cb, not_joined):
    target = message_or_cb.message if isinstance(message_or_cb, types.CallbackQuery) else message_or_cb
    
    kb = InlineKeyboardBuilder()
    for ch in not_joined:
        kb.row(InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch['url']))
    kb.row(InlineKeyboardButton(text="🔄 Verify & Start", callback_data="btn_home"))
    
    fomo_text = (
        "🚀 <b>ACCESS RESTRICTED: GOD-LEVEL POWER AWAITS!</b>\n"
        "────────────────────\n"
        "You are one step away from the world's most powerful hosting bot. 🛰\n\n"
        "❌ <b>Wait!</b> To prevent spam and keep the servers ultra-fast, you MUST join our official channels first.\n\n"
        "🔥 <b>Join them now and click VERIFY to unlock:</b>\n"
        "▪️ ♾️ Unlimited Project Slots\n"
        "▪️ ⚡ God-Speed Deployment\n"
        "▪️ 🛡 Neo Shield Protection\n\n"
        "<i>Don't miss out. The launch of the year is happening NOW!</i>"
    )
    
    img_path = "assets/neo_start_features_fomo.png"
    if os.path.exists(img_path):
        feature_img = FSInputFile(img_path)
        try:
            if isinstance(message_or_cb, types.CallbackQuery):
                await message_or_cb.message.answer_photo(photo=feature_img, caption=fomo_text, reply_markup=kb.as_markup(), parse_mode="HTML")
                await message_or_cb.message.delete()
            else:
                await message_or_cb.answer_photo(photo=feature_img, caption=fomo_text, reply_markup=kb.as_markup(), parse_mode="HTML")
        except:
            await target.answer(fomo_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await target.answer(fomo_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_states.pop(message.from_user.id, None) # Clear any pending states
    print(f"DEBUG: User {message.from_user.id} matched against Admin ID {ADMIN_ID}")
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id == message.from_user.id:
            referrer_id = None

    referrer_to_notify = database.add_user(message.from_user.id, message.from_user.username, referrer_id)
    if referrer_to_notify:
        try:
            await bot.send_message(referrer_to_notify, 
                "🎉 <b>New Referral!</b>\n\n"
                "You earned <b>$5.0</b> credits and +1 referral count.\n"
                "<i>Keep inviting to unlock more slots!</i>", 
                parse_mode="HTML")
        except Exception as e:
            print(f"Failed to notify referrer: {e}")
    
    # Sync Telegram Avatar
    try:
        photos = await bot.get_user_profile_photos(message.from_user.id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            file = await bot.get_file(file_id)
            # We store the direct telegram file link or we can download it. 
            # For simplicity, let's use the file_id or a placeholder to fetch later.
            # But the web console needs a URL. Let's use the public bot file URL or similar.
            # Actually, we can generate a temporary URL that points to our Own server which proxies the TG photo.
            avatar_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
            user = database.get_user(message.from_user.id)
            if not user.get('profile_pic') or 'telegram.org' in user.get('profile_pic', ''):
                database.update_user_avatar(message.from_user.id, avatar_url)
    except: pass

    # --- FORCE SUB CHECK ---
    not_joined = await check_fsub(message.from_user.id)
    if not_joined:
        await show_fsub_shield(message, not_joined)
        return

    # If all joined, show main menu
    kb, text = await main_menu(message.from_user.id)
    if kb is None: # Maintenance or Banned
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("🕹 **Neo Hosting Dashboard Activated.**", reply_markup=get_main_keyboard(), parse_mode="Markdown")
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "btn_web")
async def cb_web(callback: CallbackQuery):
    user_states.pop(callback.from_user.id, None) # Clear any pending states
    user = database.get_user(callback.from_user.id)
    local_note = ""
    if os.name == 'nt' and "localhost" not in WEB_URL:
        local_note = "\n\n⚠️ **Note:** You are running locally but your link uses a VPS IP. Use `http://localhost:8000` for your browser if testing on this PC."
    
    # Generate secure session token
    try:
        session_token = database.create_session(callback.from_user.id)
    except AttributeError:
        print("DB Schema update needed for sessions")
        session_token = "error"

    text = (
        f"🌐 **Web Editor Access**\n\n"
        f"Click below to login securely to your control panel.\n"
        f"<i>Link expires in 24 hours.</i>\n\n"
        f"⚠️ <u>Keep this link private! Anyone with it can edit your code.</u>"
        f"{local_note}"
    )
    
    # Append token to URL
    login_url = f"{WEB_URL}/login?token={session_token}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Open Web Editor", url=login_url)],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "btn_home")
async def cb_home(callback: CallbackQuery):
    user_states.pop(callback.from_user.id, None)
    
    # Re-check Fsub on Home/Verify
    not_joined = await check_fsub(callback.from_user.id)
    print(f"DEBUG: cb_home {callback.from_user.id} -> Checked Fsub. Missing: {[c['channel_id'] for c in not_joined]}")
    if not_joined:
        try:
            await callback.answer("❌ Join all channels first!", show_alert=True)
        except:
            print("Failed to show alert")
        await show_fsub_shield(callback, not_joined)
        return

    kb, text = await main_menu(callback.from_user.id)
    try:
        if kb is None: # Maintenance or Banned
            if text != callback.message.text:
                   await callback.message.edit_text(text, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        # Ignore message not modified or empty text errors
        if "message is not modified" not in str(e) and "there is no text" not in str(e):
            print(f"Callback Error: {e}")
            await callback.answer()

@dp.callback_query(F.data == "btn_projects")
async def cb_projects(event: Union[types.Message, types.CallbackQuery]):
    uid = event.from_user.id
    user_states.pop(uid, None)
    projects = database.get_user_projects(uid)
    
    builder = InlineKeyboardBuilder()
    if not projects:
        text = "❌ **No managed projects found.**"
    else:
        for p in projects:
            status_icon = "🟢" if p['status'] == 'running' else "🔴"
            builder.row(InlineKeyboardButton(text=f"{status_icon} {p['name']}", callback_data=f"proj_{p['project_id']}"))
        text = f"{get_premium_header('MANAGED PROJECTS')}"
    
    builder.row(InlineKeyboardButton(text="⬅️ Back Home", callback_data="btn_home"))
    
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("proj_"))
async def cb_project_manage(callback: CallbackQuery):
    project_id = callback.data.split("_")[1]
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    p = c.fetchone()
    conn.close()

    if not p:
        await callback.answer("Project not found.")
        return

    status_icon = "🟢" if p['status'] == 'running' else "⚪"
    status_label = "LIVE" if p['status'] == 'running' else "OFFLINE"
    
    # Render-style Events
    events = database.get_events(project_id, limit=3)
    ev_text = ""
    for ev in events:
        time_str = ev['timestamp'].split(' ')[1][:5]
        ev_text += f"▪️ <code>[{time_str}]</code> {ev['message'][:35]}\n"
    if not ev_text: ev_text = "<i>(No recent events)</i>"

    builder = InlineKeyboardBuilder()
    if p['status'] == 'running':
        builder.row(InlineKeyboardButton(text="⏹ STOP ENGINE", callback_data=f"ctrl_stop_{project_id}"))
    else:
        builder.row(InlineKeyboardButton(text="⚡ DEPLOY ENGINE", callback_data=f"ctrl_start_{project_id}"))
    
    builder.row(
        InlineKeyboardButton(text="📜 LIVE LOGS", callback_data=f"ctrl_live_{project_id}"),
        InlineKeyboardButton(text="📖 STATIC LOGS", callback_data=f"ctrl_logs_{project_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📸 SNAPSHOT", callback_data=f"ctrl_snap_{project_id}"),
        InlineKeyboardButton(text="📦 BACKUP", callback_data=f"ctrl_zip_{project_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 WIPE", callback_data=f"ctrl_del_{project_id}"),
        InlineKeyboardButton(text="🌍 ENVIRONMENT", callback_data=f"ctrl_env_{project_id}")
    )
    builder.row(InlineKeyboardButton(text="⬅️ BACK TO LIST", callback_data="btn_projects"))
    
    text = (
        f"<b>{status_icon} {p['name']}</b>\n"
        f"<code>{p['type'].upper()} CORE</code> • <b>{status_label}</b>\n\n"
        f"📅 <b>Recent Activity (Events):</b>\n{ev_text}\n"
        f"🌐 <b>Web ID:</b> <code>user_{project_id[:6]}</code>"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("ctrl_"))
async def cb_project_control(callback: CallbackQuery):
    _, action, project_id = callback.data.split("_")
    
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    p = c.fetchone()
    conn.close()

    if not p:
        await callback.answer("Project not found.")
        return

    if action == "start":


        await callback.message.edit_text("⏳ **Engine Booting...**", parse_mode="Markdown")
        success, res = manager.start_project(project_id, p['type'], p['entry_point'])
        
        if success:
            database.update_project_status(project_id, "running")
            # Wait and check for live errors
            await asyncio.sleep(3)
            logs = manager.get_logs(project_id, 15)
            if "Traceback" in logs or "Error" in logs or "Exception" in logs:
                user = database.get_user(callback.from_user.id)
                eb = InlineKeyboardBuilder()
                eb.row(InlineKeyboardButton(text="📝 Edit Code", url=f"{WEB_URL}/edit/{project_id}"))
                eb.row(InlineKeyboardButton(text="⬅️ Back", callback_data=f"proj_{project_id}"))
                
                err_text = (
                    f"⚠️ **DEPLOYMENT ERROR DETECTED!**\n\n"
                    f"```\n{logs[-1000:]}\n```\n\n"
                    f"💡 **How to fix?**\n"
                    f"1. Click 'Edit Code' below\n"
                    f"2. Login using:\n"
                    f"   ID: `{user['web_id']}`\n"
                    f"   Pass: `{user['password']}`\n"
                    f"3. Fix the syntax and click 'Deploy'."
                )
                await callback.message.answer(err_text, reply_markup=eb.as_markup(), parse_mode="Markdown")
        else:
            await callback.message.answer(f"❌ **BOOT FAILED!**\nReason: `{res}`", parse_mode="Markdown")
            
    elif action == "stop":
        manager.stop_project(project_id)
        database.update_project_status(project_id, "stopped")
        await callback.answer("⏹ Engine Offline")
        
    elif action == "logs":
        logs = manager.get_logs(project_id, 30)
        await callback.message.answer(f"📖 **Raw Terminal Output:**\n\n```\n{logs or 'No logs available.'}\n```", parse_mode="Markdown")
        return

    elif action == "zip":
        await callback.answer("⏳ Generating Backup...")
        zip_path = manager.get_project_zip(project_id)
        if zip_path:
            await callback.message.answer_document(FSInputFile(zip_path), caption=f"📦 Backup: {project_id}")
        else:
            await callback.answer("❌ Backup Failed!")
        return

    elif action == "snap":
        manager.create_snapshot(project_id)
        await callback.answer("📸 Snapshot created successfully!")
        await cb_project_manage(callback)
        return

    elif action == "del":
        manager.delete_project_files(project_id)
        database.delete_project(project_id)
        await callback.answer("🗑 Project Wiped.")
        await cb_projects(callback)
        return

    elif action == "live":
        await callback.answer("⚡ Starting Live Tail...")
        msg = await callback.message.answer(f"📺 <b>Live Terminal: {project_id}</b>\n\n<code>Initializing...</code>", parse_mode="HTML")
        
        async def live_tail():
            for _ in range(15): # 30 seconds of live logs
                logs = manager.get_logs(project_id, 15)
                # Clean logs for HTML
                logs_safe = logs.replace("<", "&lt;").replace(">", "&gt;")
                try:
                    await msg.edit_text(f"📺 <b>Live Terminal: {project_id}</b>\n\n<pre>{logs_safe or 'Waiting for logs...'}</pre>", parse_mode="HTML")
                except: break
                await asyncio.sleep(2)
            await msg.edit_text(f"📺 <b>Live Terminal: {project_id}</b>\n\n<i>Live session ended. Click 'Live Logs' again to resume.</i>\n\n<pre>{logs_safe or '---'}</pre>", parse_mode="HTML")
            
        asyncio.create_task(live_tail())
        return

    elif action == "env":
        envs = database.get_project_envs(project_id)
        text = f"🌍 <b>Environment Variables:</b> `{p['name']}`\n\n"
        kb = InlineKeyboardBuilder()
        for k in envs:
            text += f"▪️ `{k}`: `••••••••`\n"
            kb.row(InlineKeyboardButton(text=f"🗑 Delete {k}", callback_data=f"ev_del_{project_id}_{k}"))
        
        if not envs: text += "<i>No variables set.</i>\n\n"
        text += "\nTo add, send: `KEY=VALUE`"
        kb.row(InlineKeyboardButton(text="➕ Add Variable", callback_data=f"ev_add_{project_id}"))
        kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data=f"proj_{project_id}"))
        await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
        return

    await cb_project_manage(callback)

@dp.callback_query(F.data.startswith("ev_"))
async def cb_env_control(callback: CallbackQuery):
    _, action, pid, *rest = callback.data.split("_")
    if action == "add":
        user_states[callback.from_user.id] = f"waiting_for_env_{pid}"
        await callback.answer("Send KEY=VALUE now.")
        await callback.message.answer("⌨️ <b>Send your Environment Variable:</b>\nExample: `BOT_TOKEN=12345:ABC`", parse_mode="HTML")
    elif action == "del":
        key = rest[0]
        database.delete_project_env(pid, key)
        await callback.answer(f"🗑 {key} Deleted.")
        # Refresh UI (manually calling logic)
        callback.data = f"ctrl_env_{pid}"
        await cb_project_control(callback)

@dp.callback_query(F.data == "btn_upgrade")
async def cb_upgrade(event: Union[types.Message, types.CallbackQuery]):
    user_states.pop(event.from_user.id, None)
    text = (
        "💎 <b>Choose Your Power Level</b>\n"
        "────────────────────\n\n"
        "<b>[ FREE ] — $0/mo</b>\n"
        "▪️ 1 Project Slot\n"
        "▪️ Basic Monitoring\n"
        "▪️ Community Support\n\n"
        "<b>[ PROFESSIONAL ] — $5/mo</b>\n"
        "▪️ 10 Project Slots\n"
        "▪️ ⚡ Priority CPU/RAM\n"
        "▪️ Live Terminal Logs\n"
        "▪️ Managed Envs\n\n"
        "<b>[ VIP ENTERPRISE ] — $15/mo</b>\n"
        "▪️ ♾️ Infinite Slots\n"
        "▪️ 🔥 God-Level Performance\n"
        "▪️ 7/24 Private Support\n"
        "▪️ Neo Shield Protection\n\n"
        "<i>Select a plan to contact management.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Professional", url="https://t.me/Rytce"), InlineKeyboardButton(text="👑 VIP", url="https://t.me/Rytce")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home")]
    ])
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")

# (Other handlers for upload, clone, refer, etc. omitted but implied as they work)
# Re-adding them properly
@dp.callback_query(F.data == "btn_upload")
async def cb_upload(callback: CallbackQuery):
    user = database.get_user(callback.from_user.id)
    if not user:
        database.add_user(callback.from_user.id, callback.from_user.username or "Unknown")
        user = database.get_user(callback.from_user.id)
        
    projects = database.get_user_projects(callback.from_user.id)
    if len(projects) >= user['slots']:
        await callback.answer("❌ Slots Full!")
        return
    user_states[callback.from_user.id] = "waiting_for_file"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Quick Deploy (Templates)", callback_data="btn_market")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home")]
    ])
    await callback.message.edit_text("📤 **Project Upload**\n\nSend me a `.py`, `.js` or `.zip` file, or use a template:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "btn_clone")
async def cb_clone(callback: CallbackQuery):
    user = database.get_user(callback.from_user.id)
    if not user:
        database.add_user(callback.from_user.id, callback.from_user.username or "Unknown")
        user = database.get_user(callback.from_user.id)
        
    projects = database.get_user_projects(callback.from_user.id)
    if len(projects) >= user['slots']:
        await callback.answer("❌ Slots Full!")
        return
    user_states[callback.from_user.id] = "waiting_for_repo"
    await callback.message.edit_text("🐙 **GitHub Clone**\n\nSend Repo URL (e.g. `https://github.com/user/repo`)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home")]]), parse_mode="Markdown")

@dp.message(F.text.startswith("http"))
async def handle_repo(message: types.Message):
    uid = message.from_user.id
    if user_states.get(uid) != "waiting_for_repo": return
    
    # Ignore if it's our own console link
    if WEB_URL in message.text:
        return
        
    project_id = str(uuid.uuid4())[:8]
    ms = await message.answer("🐙 **Cloning...**", parse_mode="Markdown")
    success, err = manager.clone_repo(message.text, project_id)
    
    user_states.pop(uid, None) # Clear state immediately after attempt
    if not success:
        await ms.edit_text(f"❌ Clone Error: {err}")
        return
    ep = manager.detect_entry_point(project_id)
    pt = "js" if ep.endswith(".js") else "py"
    await ms.edit_text("📦 **Installing dependencies...**", parse_mode="Markdown")
    await asyncio.to_thread(manager.create_project_env, project_id, pt)
    
    database.add_project(project_id, uid, message.text.split('/')[-1], pt, str(manager.BASE_DIR/project_id), ep)
    
    # Auto-Extract Envs if they exist in repo
    detected_envs = manager.extract_env_from_files(project_id)
    for k, v in detected_envs.items():
        database.set_project_env(project_id, k, v)
    
    # Analyze & Request Approval
    audit = manager.get_source_audit(project_id, uid)
    report = f"🛡 **APPROVAL REQUEST**\n\n" \
             f"User: `{uid}`\n" \
             f"Project: `{project_id}`\n" \
             f"Engine: `{audit['engine']}`\n" \
             f"AI Audit: {audit['ai_audit'][:500]}..."
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{project_id}"), 
         InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{project_id}")]
    ])
    try:
        await bot.send_message(ADMIN_ID, report, reply_markup=kb, parse_mode="HTML")
    except: pass

    user_states[uid] = None
    await ms.edit_text(f"⏳ **Pending Approval**\n\nYour project `{project_id}` has been submitted for review. You will be notified once approved.", parse_mode="Markdown")

@dp.callback_query(F.data.startswith("approve_"))
async def cb_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    project_id = callback.data.split("_")[1]
    database.approve_project(project_id)
    
    # Get user to notify
    projects = database.get_all_projects() # Inefficient but simple for now
    target_user = next((p['user_id'] for p in projects if p['project_id'] == project_id), None)
    
    await callback.message.edit_text(f"✅ **Approved Project {project_id}**", parse_mode="Markdown")
    if target_user:
        try: await bot.send_message(target_user, f"✅ **Project Approved!**\n\nYour bot `{project_id}` is now ready to deploy.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Control Panel", callback_data=f"proj_{project_id}")]]))
        except: pass

@dp.callback_query(F.data.startswith("reject_"))
async def cb_reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    project_id = callback.data.split("_")[1]
    manager.delete_project_files(project_id)
    await callback.message.edit_text(f"❌ **Rejected Project {project_id}**", parse_mode="Markdown")

@dp.message(F.document)
async def handle_docs(message: types.Message):
    if user_states.get(message.from_user.id) != "waiting_for_file": return
    project_id = str(uuid.uuid4())[:8]
    ext = message.document.file_name.split('.')[-1]
    ms = await message.answer("📥 **Uploading...**", parse_mode="Markdown")
    
    # Ensure directory exists before download
    upload_dir = Path("god_host/projects")
    upload_dir.mkdir(parents=True, exist_ok=True)
    fpath = upload_dir / f"{project_id}_{message.document.file_name}"
    
    await bot.download(message.document.file_id, destination=fpath)
    pt = "js" if ext == "js" else "py"

# ... (skipping to next hunk) ...

    if ext == "zip":
        manager.extract_zip(fpath, project_id); os.remove(fpath)
        ep = manager.detect_entry_point(project_id)
    else:
        # Move file to project directory
        pdir = manager.BASE_DIR / project_id
        os.makedirs(pdir, exist_ok=True)
        shutil.move(fpath, pdir / message.document.file_name)
        ep = message.document.file_name

    await ms.edit_text("⚙️ **Setting up Environment...**", parse_mode="Markdown")
    await asyncio.to_thread(manager.create_project_env, project_id, pt)
    database.add_project(project_id, message.from_user.id, message.document.file_name, pt, str(manager.BASE_DIR/project_id), ep)
    
    # Auto-Extract Envs if they exist in zip/file
    detected_envs = manager.extract_env_from_files(project_id)
    for k, v in detected_envs.items():
        database.set_project_env(project_id, k, v)
    
    # Analyze & Request Approval
    audit = manager.get_source_audit(project_id, message.from_user.id)
    
    import html # Import here to avoid global changes, or could move to top
    safe_uid = html.escape(str(message.from_user.id))
    safe_pid = html.escape(str(project_id))
    safe_eng = html.escape(str(audit['engine']))
    safe_audit = html.escape(str(audit['ai_audit'])[:500])

    report = f"🛡 <b>APPROVAL REQUEST</b>\n\n" \
             f"User: <code>{safe_uid}</code>\n" \
             f"Project: <code>{safe_pid}</code>\n" \
             f"Engine: <code>{safe_eng}</code>\n" \
             f"AI Audit: {safe_audit}..."
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{project_id}"), 
         InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{project_id}")]
    ])
    LOG_CHANNEL_ID = manager.LOG_CHANNEL_ID
    
    try:
        # 1. Forward to Admin for Approval
        await message.forward(ADMIN_ID)
        await bot.send_message(ADMIN_ID, report, reply_markup=kb, parse_mode="HTML")
        
        # 2. Log to Channel (Backup/Store)
        if LOG_CHANNEL_ID:
            await message.forward(LOG_CHANNEL_ID)
            await bot.send_message(LOG_CHANNEL_ID, report, parse_mode="HTML")
            
    except Exception as e:
        print(f"ERROR: Failed to send notifications (Admin/Channel): {e}", flush=True)

    user_states[message.from_user.id] = None
    await ms.edit_text(f"⏳ **Pending Approval**\n\nYour project `{project_id}` has been submitted for review. You will be notified once approved.", parse_mode="Markdown")

@dp.callback_query(F.data == "btn_wallet")
async def cb_wallet(callback: CallbackQuery):
    user = database.get_user(callback.from_user.id)
    if not user:
        database.add_user(callback.from_user.id, callback.from_user.username or "Unknown")
        user = database.get_user(callback.from_user.id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Funds", callback_data="btn_add_funds"), InlineKeyboardButton(text="📜 History", callback_data="btn_history")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home")]
    ])
    await callback.message.edit_text(
        f"💰 **Wallet**\n\n" \
        f"💵 <b>Current Balance:</b> <code>${user.get('balance', 0.0):.2f}</code>\n" \
        f"💳 <b>Transactions:</b> 0 (Coming Soon)",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "btn_stats")
async def cb_stats(event: Union[types.Message, types.CallbackQuery]):
    uid = event.from_user.id
    user_states.pop(uid, None)
    user = database.get_user(uid)
    if not user:
        database.add_user(uid, event.from_user.username or "Unknown")
        user = database.get_user(uid)
        if not user: return # Should not happen
    expiry = user.get('plan_expiry') or "Permanent"
    text = f"{get_premium_header('ACCOUNT STATS')}\n\n" \
           f"📅 <b>Joined:</b> <code>{user['joined_at']}</code>\n" \
           f"⭐ <b>Plan:</b> <code>{user.get('plan', 'FREE')}</code>\n" \
           f"⏳ <b>Expiry:</b> <code>{expiry}</code>\n" \
           f"👥 <b>Referrals:</b> <code>{user['referrals']}</code>\n" \
           f"📦 <b>Slots:</b> <code>{user['slots']}</code>\n" \
           f"💰 <b>Balance:</b> <code>${user.get('balance', 0.0):.2f}</code>\n" \
           f"🆔 <b>Web ID:</b> <code>{user['web_id']}</code>"
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🎁 REDEEM CODE", callback_data="btn_redeem"))
    kb.row(InlineKeyboardButton(text="🏆 LEADERBOARD", callback_data="btn_leaderboard"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home"))
    
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "btn_referral")
async def cb_ref(callback: CallbackQuery):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={callback.from_user.id}"
    await callback.message.edit_text(f"🤝 **Invite & Earn**\n\nInvite 3 friends to get 1 extra slot!\n\n**Link:** `{link}`", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home")]]), parse_mode="Markdown")

@dp.callback_query(F.data == "btn_admin")
async def cb_admin(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    m_icon = "🟢" if not database.is_maintenance() else "🔴"
    text = f"{get_premium_header('ADMIN PANEL')}\n\n" \
           f"Total Users: {database.get_total_users()}\n" \
           f"Total Projects: {database.get_total_projects()}\n\n" \
           f"Select an action:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Manage User", callback_data="admin_manage_user")],
        [InlineKeyboardButton(text="🎁 Gift Code Factory", callback_data="admin_gift_factory")],
        [InlineKeyboardButton(text="📢 Channel Manager", callback_data="admin_channels")],
        [InlineKeyboardButton(text="📊 Revenue Status", callback_data="admin_revenue")],
        [InlineKeyboardButton(text="📂 Global Projects", callback_data="admin_projects")],
        [InlineKeyboardButton(text="🛡 Blacklist Manager", callback_data="admin_blacklist")],
        [InlineKeyboardButton(text=f"{m_icon} Toggle Maintenance", callback_data="admin_toggle_mt")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 System Stats", callback_data="admin_sys")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_projects")
async def cb_admin_all_projects(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    projects = database.get_all_projects()
    kb = InlineKeyboardBuilder()
    for p in projects:
        status_icon = "🟢" if p['status'] == 'running' else "🔴"
        kb.row(InlineKeyboardButton(text=f"{status_icon} {p['name']} (UID: {p['user_id']})", callback_data=f"proj_{p['project_id']}"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="btn_admin"))
    await callback.message.edit_text("📂 **Global Project Oversight**", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "admin_blacklist")
async def cb_admin_blacklist(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    patterns = database.get_blacklist()
    text = "🛡 **Neo Shield Blacklist**\n\nClick a pattern to remove it, or send a new one to add it."
    kb = InlineKeyboardBuilder()
    for p in patterns:
        kb.row(InlineKeyboardButton(text=f"🗑 {p}", callback_data=f"bl_rem_{p}"))
    kb.row(InlineKeyboardButton(text="➕ Add Pattern", callback_data="bl_add"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="btn_admin"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "bl_add")
async def cb_bl_add(callback: CallbackQuery):
    user_states[callback.from_user.id] = "waiting_for_blacklist_pattern"
    await callback.message.edit_text("⚙️ **Add Blacklist Pattern**\n\nSend the code pattern you want to block (e.g. `import os` or `os.remove`).", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_blacklist")]]))

@dp.callback_query(F.data.startswith("bl_rem_"))
async def cb_bl_rem(callback: CallbackQuery):
    pattern = callback.data.replace("bl_rem_", "")
    database.remove_blacklist_pattern(pattern)
    await callback.answer(f"Removed: {pattern}")
    await cb_admin_blacklist(callback)

@dp.callback_query(F.data == "admin_toggle_mt")
async def cb_admin_mt(callback: CallbackQuery):
    curr = database.is_maintenance()
    database.set_maintenance(not curr)
    await callback.answer(f"Maintenance: {'ON' if not curr else 'OFF'}")
    await cb_admin(callback)

@dp.callback_query(F.data == "admin_manage_user")
async def cb_admin_mu(callback: CallbackQuery):
    user_states[callback.from_user.id] = "waiting_for_user_id"
    await callback.message.edit_text("👤 <b>Manage User</b>\n\nSend me the <code>User ID</code> of the person you want to manage.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="btn_admin")]]), parse_mode="HTML")

@dp.callback_query(F.data == "admin_sys")
async def cb_admin_sys(callback: CallbackQuery):
    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    text = f"{get_premium_header('SYSTEM STATS')}\n\n" \
           f"💻 CPU: `{cpu}%` / 🚀 RAM: `{ram}%`"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="btn_admin")]]), parse_mode="Markdown")

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_bc(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    user_states[callback.from_user.id] = "waiting_for_broadcast"
    await callback.message.edit_text("📢 **Send Message**\n\nType the message you want to broadcast to all users.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="btn_admin")]]), parse_mode="Markdown")

@dp.callback_query(F.data == "admin_revenue")
async def cb_admin_revenue(callback: CallbackQuery):
    stats = database.get_global_stats()
    text = (
        f"{get_premium_header('REVENUE & USAGE')}\n\n"
        f"👥 **Total Users:** <code>{stats['users']}</code>\n"
        f"👑 **VIP Users:** <code>{stats['vip']}</code>\n"
        f"📁 **Total Projects:** <code>{stats['projects']}</code>\n"
        f"🟢 **Running Now:** <code>{stats['running']}</code>\n"
        f"💰 **Total Balance:** <code>${stats['revenue']:.2f}</code>\n\n"
        f"<i>Status: Profitable 📈</i>"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="btn_admin")]]), parse_mode="HTML")

@dp.callback_query(F.data == "admin_channels")
async def cb_admin_channels(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    channels = database.get_channels()
    text = "📢 **Channel Manager**\n\nAdd or remove channels that users must join."
    kb = InlineKeyboardBuilder()
    for ch in channels:
        type_str = "🔹 Force" if ch['is_force'] else "🔸 Opt"
        kb.row(
            InlineKeyboardButton(text=f"🗑 {ch['name']}", callback_data=f"ch_del_{ch['channel_id']}"),
            InlineKeyboardButton(text=f"✏️ Edit", callback_data=f"ch_edit_{ch['channel_id']}")
        )
    
    kb.row(InlineKeyboardButton(text="➕ Add New Channel", callback_data="ch_add"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="btn_admin"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("ch_edit_"))
async def cb_ch_edit(callback: CallbackQuery):
    ch_id = callback.data.replace("ch_edit_", "")
    channels = database.get_channels()
    ch = next((c for c in channels if str(c['channel_id']) == ch_id), None)
    if not ch: return await callback.answer("Not found.")
    
    await callback.message.edit_text(
        f"✏️ **Edit Channel: {ch['name']}**\n\n"
        f"**Current ID:** `{ch['channel_id']}`\n"
        f"**Current URL:** `{ch['url']}`\n\n"
        "To update, send new data in this format:\n"
        f"<code>{ch['channel_id']} | New Name | New URL | {ch['is_force']}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_channels")]])
    )
    user_states[callback.from_user.id] = "waiting_for_channel_data"

@dp.callback_query(F.data == "ch_add")
async def cb_ch_add(callback: CallbackQuery):
    user_states[callback.from_user.id] = "waiting_for_channel_data"
    await callback.message.edit_text(
        "📝 **Add Channel**\n\nSend data in this format:\n"
        "<code>ChannelID | Name | URL | ForceLevel</code>\n\n"
        "✨ **ForceLevel Guide:**\n"
        "▪️ Type <code>1</code> for Mandatory (Force Sub)\n"
        "▪️ Type <code>0</code> for Optional\n\n"
        "Example:\n<code>-100123 | My Channel | t.me/link | 1</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="admin_channels")]])
    )

@dp.callback_query(F.data.startswith("ch_del_"))
async def cb_ch_del(callback: CallbackQuery):
    ch_id = callback.data.replace("ch_del_", "")
    database.delete_channel(ch_id)
    await callback.answer("Channel Removed.")
    await cb_admin_channels(callback)
async def cb_admin_gift(callback: CallbackQuery):
    text = "🎁 **Gift Code Factory**\n\nSelect a plan to generate codes for:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="PRO ($5)", callback_data="gen_pro"), InlineKeyboardButton(text="VIP ($15)", callback_data="gen_vip")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="btn_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("gen_"))
async def cb_gen_start(callback: CallbackQuery):
    plan = callback.data.split("_")[1].upper()
    user_states[callback.from_user.id] = f"waiting_for_gift_count_{plan}"
    await callback.message.edit_text(f"🔢 How many **{plan}** codes do you want to generate?")

@dp.callback_query(F.data.startswith("mu_"))
async def cb_mu_choice(callback: CallbackQuery):
    _, action, target_id = callback.data.split("_")
    target_id = int(target_id)
    
    if action == "pro":
        database.update_user_status(target_id, plan="PRO", slots_add=5)
        await callback.answer("User Upgraded to PRO!")
    elif action == "vip":
        database.update_user_status(target_id, plan="VIP", slots_add=15)
        await callback.answer("User Upgraded to VIP!")
    elif action == "slot":
        database.update_user_status(target_id, slots_add=1)
        await callback.answer("+1 Slot Added!")
    elif action == "ban":
        database.update_user_status(target_id, ban=True)
        await callback.answer("User BANNED!")
    elif action == "unban":
        database.update_user_status(target_id, ban=False)
        await callback.answer("User Unbanned.")
    elif action == "peek":
        projects = database.get_user_projects(target_id)
        if not projects:
            await callback.answer("No projects to peek.")
            return
        kb = InlineKeyboardBuilder()
        for p in projects:
            kb.row(InlineKeyboardButton(text=f"📂 {p['name']}", url=f"{WEB_URL}/edit/{p['project_id']}"))
        kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data=f"mu_manage_{target_id}"))
        await callback.message.edit_text(f"🕵️ **Inspecting Projects for {target_id}:**", reply_markup=kb.as_markup())
        return
        
    await msg_manage_user_ui(callback.message, target_id)

async def msg_manage_user_ui(message, target_id):
    user = database.get_user(target_id)
    if not user:
        try:
            await message.edit_text("❌ User not found.")
        except:
            await message.answer("❌ User not found.")
        return
        
    text = f"👤 <b>User Info:</b> <code>{target_id}</code>\n" \
           f"⭐ <b>Plan:</b> {user.get('plan', 'FREE')}\n" \
           f"📦 <b>Slots:</b> {user['slots']}\n" \
           f"🚫 <b>Banned:</b> {'Yes' if user.get('is_banned') else 'No'}\n\n" \
           f"Select action:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Set PRO", callback_data=f"mu_pro_{target_id}"), InlineKeyboardButton(text="👑 Set VIP", callback_data=f"mu_vip_{target_id}")],
        [InlineKeyboardButton(text="➕ Add Slot", callback_data=f"mu_slot_{target_id}"), InlineKeyboardButton(text="🕵️ Peek Projects", callback_data=f"mu_peek_{target_id}")],
        [InlineKeyboardButton(text="🚫 BAN", callback_data=f"mu_ban_{target_id}"), InlineKeyboardButton(text="✅ Unban", callback_data=f"mu_unban_{target_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="admin_manage_user")]
    ])
    
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    state = user_states.get(uid)
    
    if state == "waiting_for_channel_data" and uid == ADMIN_ID:
        user_states.pop(uid, None)
        try:
            parts = message.text.split("|")
            if len(parts) < 4:
                raise ValueError("Missing parts")
            
            cid = parts[0].strip()
            name = parts[1].strip()
            url = parts[2].strip()
            force_raw = parts[3].strip().lower()
            
            # Logic for Force: 1, yes, true = 1 | 0, no, false = 0
            is_force = 1 if force_raw in ['1', 'yes', 'true'] or "force" in force_raw else 0
            
            database.add_channel(cid, name, url, is_force)
            await message.reply(f"✅ Channel **{name}** added/updated successfully!", parse_mode="Markdown")
        except Exception as e:
            await message.reply("❌ **Invalid Format!**\n\nPlease use: `ID | Name | URL | 1 or 0`", parse_mode="Markdown")
        
    elif state == "waiting_for_broadcast" and uid == ADMIN_ID:
        users = database.get_all_users()
        count = 0
        for u in users:
            try:
                target_uid = u['user_id']
                if target_uid == uid: continue
                await bot.send_message(target_uid, f"📢 **ADMIN BROADCAST**\n\n{message.text}", parse_mode="HTML")
                count += 1
            except: continue
        user_states.pop(uid, None)
        await message.reply(f"✅ Sent to {count} users.")
    
    elif state == "waiting_for_user_id" and uid == ADMIN_ID:
        if not message.text.isdigit():
            await message.reply("❌ Please send a valid numeric User ID.")
            return
        user_states.pop(uid, None)
        await msg_manage_user_ui(message, int(message.text))
    
    elif state and state.startswith("waiting_for_gift_count_") and uid == ADMIN_ID:
        plan = state.split("_")[-1]
        try:
            count = int(message.text)
            slots = 10 if plan == "PRO" else 50
            codes = database.generate_gift_codes(plan, slots, count)
            code_str = "\n".join([f"<code>{c}</code>" for c in codes])
            await message.reply(f"✅ **Generated {count} {plan} Codes:**\n\n{code_str}", parse_mode="HTML")
        except:
            await message.reply("❌ Invalid count.")
        user_states.pop(uid, None)
    
    elif state == "waiting_for_redeem":
        success, res = database.redeem_gift_code(uid, message.text.strip())
        user_states.pop(uid, None)
        await message.reply(res)
    
    elif state == "waiting_for_repo":
        await handle_repo(message)
        
    elif state and state.startswith("waiting_for_env_"):
        pid = state.replace("waiting_for_env_", "")
        if "=" in message.text:
            key, val = message.text.split("=", 1)
            database.set_project_env(pid, key.strip(), val.strip())
            user_states.pop(uid, None)
            await message.answer(f"✅ <b>Variable Saved:</b> `{key.strip()}`\nRestart project to apply changes.", parse_mode="HTML")
        else:
            await message.answer("❌ Invalid format. Use `KEY=VALUE`.")
            
    elif state == "waiting_for_file":
        await message.reply("❌ Please send the project file as a **Document**, not text.")

    # Reply Keyboard Handlers
    elif state == "waiting_for_blacklist_pattern" and uid == ADMIN_ID:
        database.add_blacklist_pattern(message.text.strip())
        user_states.pop(uid, None)
        await message.reply(f"✅ Pattern `{message.text}` added to Neo Shield.")
        
    elif message.text == "📊 MY ACCOUNT":
        await cb_stats(message)
    elif message.text == "💰 WALLET":
        await cb_wallet(message)
    elif message.text == "💎 UPGRADE":
        await cb_upgrade(message)
    elif message.text == "📁 MY PROJECTS":
        await cb_projects(message)

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    start_time = time.time()
    msg = await message.answer("🏓 Pinging...")
    end_time = time.time()
    latency = round((end_time - start_time) * 1000)
    
    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    await msg.edit_text(
        f"🚀 **PONG!**\n\n"
        f"🛰 **Latency:** `{latency}ms`\n"
        f"💻 **CPU:** `{cpu}%`\n"
        f"🔋 **RAM:** `{ram}%`"
    )

async def self_healing_monitor():
    """Background task to restart crashed projects."""
    while True:
        try:
            conn = database.get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM projects WHERE status = 'running'")
            running_projs = c.fetchall()
            conn.close()
            
            for p in running_projs:
                pid = p['project_id']
                stats = manager.get_project_stats(pid)
                if stats['status'] == "Crashing" or stats['status'] == "Offline":
                    print(f"🔄 Self-Healing: Restarting {pid}...")
                    manager.start_project(pid, p['type'], p['entry_point'])
        except Exception as e:
            print(f"⚠️ Monitor Error: {e}")
        await asyncio.sleep(60) # Check every minute

# Removed redundant text handler

@dp.callback_query(F.data == "btn_market")
async def cb_market(callback: CallbackQuery):
    templates = database.get_templates()
    text = f"{get_premium_header('🏪 MARKETPLACE')}\n\nSelect a template to deploy instantly:"
    kb = InlineKeyboardBuilder()
    for t in templates:
        kb.row(InlineKeyboardButton(text=f"🚀 {t['name']}", callback_data=f"tmpl_{t['template_id']}"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("tmpl_"))
async def cb_tmpl_view(callback: CallbackQuery):
    tmpl_id = callback.data.split("_")[1]
    templates = database.get_templates()
    t = next((x for x in templates if x['template_id'] == tmpl_id), None)
    if not t: return
    
    text = f"<b>{t['name']}</b>\n<i>{t['category']}</i>\n\n{t['description']}\n\n" \
           f"🔗 <b>Source:</b> <a href='{t['repo_url']}'>GitHub</a>"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💥 DEPLOY NOW", callback_data=f"deploy_tmpl_{tmpl_id}"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="btn_market"))
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("deploy_tmpl_"))
async def cb_tmpl_deploy(callback: CallbackQuery):
    # Logic similar to handle_repo
    tmpl_id = callback.data.split("_")[2]
    user = database.get_user(callback.from_user.id)
    projects = database.get_user_projects(callback.from_user.id)
    if len(projects) >= user['slots']:
        await callback.answer("❌ No free slots!")
        return
        
    templates = database.get_templates()
    t = next((x for x in templates if x['template_id'] == tmpl_id), None)
    
    ms = await callback.message.answer(f"📦 **Deploying {t['name']}...**", parse_mode="Markdown")
    project_id = str(uuid.uuid4())[:8]
    success, err = manager.clone_repo(t['repo_url'], project_id)
    if not success:
        await ms.edit_text(f"❌ Deploy Error: {err}")
        return
        
    ep = manager.detect_entry_point(project_id)
    pt = "js" if ep.endswith(".js") else "py"
    await ms.edit_text("⚙️ **Configuring Engine...**", parse_mode="Markdown")
    await asyncio.to_thread(manager.create_project_env, project_id, pt)
    database.add_project(project_id, callback.from_user.id, t['name'], pt, str(manager.BASE_DIR/project_id), ep)
    
    await ms.edit_text(f"✅ **{t['name']} Deployed!**", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Control Panel", callback_data=f"proj_{project_id}")]]), parse_mode="Markdown")

@dp.callback_query(F.data == "btn_wallet")
async def cb_wallet(event: Union[types.Message, types.CallbackQuery]):
    uid = event.from_user.id
    user = database.get_user(uid)
    text = f"{get_premium_header('💰 WALLET')}\n\n" \
           f"💵 <b>Current Balance:</b> <code>${user.get('balance', 0.0):.2f}</code>\n" \
           f"🔑 <b>UPI:</b> <code>neo.farhan@fam</code>\n\n" \
           "<i>To deposit, send funds via UPI and 'Contact Support' with your User ID. Automatic crypto gateway coming soon!</i>"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💳 Add Funds (UPI)", url="https://t.me/Rytce"))
    kb.row(InlineKeyboardButton(text="⬅️ Back", callback_data="btn_home"))
    
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "btn_leaderboard")
async def cb_leaderboard(callback: CallbackQuery):
    lb = database.get_leaderboard()
    text = f"{get_premium_header('🏆 TOP REFERRERS')}\n\n"
    for i, u in enumerate(lb):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "👤"
        name = u['username'] or f"User {u['user_id']}"
        text += f"{medal} <b>{name}</b>: <code>{u['referrals']} Refs</code>\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="btn_stats")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "btn_help")
@dp.message(Command("help"))
async def cb_help(event: Union[types.Message, types.CallbackQuery]):
    text = (
        f"{get_premium_header('📚 HELP CENTER')}\n\n"
        f"<b>1️⃣ How to Upload?</b>\n"
        f"Click 🚀 <b>UPLOAD</b> and send your `.py`, `.js` or `.zip` file. The bot will automatically create a virtual environment and install your requirements.\n\n"
        f"<b>2️⃣ GitHub Cloning</b>\n"
        f"Click 🐙 <b>CLONE</b> and send the Repo URL. Public repos work instantly!\n\n"
        f"<b>3️⃣ Web Console Access</b>\n"
        f"Use 🖥 <b>WEB ACCESS</b> to get your login ID and Password. You can edit files directly in your browser!\n\n"
        f"<b>4️⃣ Environment Variables</b>\n"
        f"Go to project settings ➡️ <b>ENVIRONMENT</b> and send <code>KEY=VALUE</code> to add secrets (like Tokens).\n\n"
        f"<b>5️⃣ Upgrading</b>\n"
        f"Visit 💎 <b>UPGRADE</b> to unlock more project slots and high-performance CPUs."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back Home", callback_data="btn_home")]])
    
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "btn_redeem")
async def cb_redeem(callback: CallbackQuery):
    user_states[callback.from_user.id] = "waiting_for_redeem"
    await callback.message.edit_text("🎁 **Redeem Gift Code**\n\nPlease enter your gift code below:", 
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="btn_stats")]]), 
                                     parse_mode="Markdown")

async def performance_monitor_task():
    """Periodically logs performance for all projects."""
    while True:
        try:
            manager.log_all_project_stats()
        except Exception as e:
            print(f"Stats Log Error: {e}")
        await asyncio.sleep(300) # Every 5 minutes

async def start_all():
    manager.cleanup_orphans()
    database.init_db()
    
    # Cleanup ghost projects from DB (whose folders are gone)
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT project_id FROM projects")
    all_p = [r[0] for r in c.fetchall()]
    for pid in all_p:
        if not (manager.BASE_DIR / pid).exists():
            print(f"🗑 Cleaning ghost project from DB: {pid}")
            c.execute("DELETE FROM projects WHERE project_id = ?", (pid,))
    conn.commit()
    conn.close()
    
    # Auto-restart running projects (Critical for Railway Persistence)
    restarted_count = manager.auto_restart_projects()
    print(f"🚀 Host-God Auto-Restart: Revived {restarted_count} projects.", flush=True)
    
    asyncio.create_task(self_healing_monitor())
    asyncio.create_task(performance_monitor_task())
    
    # Startup configuration for Railway
    global WEB_URL, PORT
    WEB_URL = os.getenv("WEB_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN") or "http://localhost:8000"
    if WEB_URL.endswith("/"): WEB_URL = WEB_URL[:-1] # Strip trailing slash
    if WEB_URL and not WEB_URL.startswith("http"):
        WEB_URL = f"https://{WEB_URL}"

    # Railway automatically sets PORT
    PORT = int(os.getenv("PORT", 8000))
    print(f"🚀 Railway Deployment Active: {WEB_URL} on PORT {PORT}", flush=True)

    import uvicorn
    # Use global PORT variable
    config = uvicorn.Config(editor.app, host="0.0.0.0", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    await asyncio.gather(dp.start_polling(bot), server.serve())

if __name__ == "__main__":
    asyncio.run(start_all())

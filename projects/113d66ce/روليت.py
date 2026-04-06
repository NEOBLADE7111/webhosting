# -*- coding: utf-8 -*-
#الملف اول مرا واول شخص ينزله BBBBYB2 يمنع منعا باتأ بيعه  تم تنزيله  مجانأ

# تم تصحيح الاخطاء Roman
#BY @S5BB5 - @ABYWQ
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, ChatMember
import uuid
import re
import random
from kvsqlite.sync import Client as DB
from datetime import date
import time
import json

API_TOKEN = '8529424912:AAEcTnDZVTrtf0nwSkbhAf03okyneQlctqU' #توكنك
bot = telebot.TeleBot(API_TOKEN)
ownerID = 7697988854 #ايدك
botdb = DB("database.db")
db_key = "db" + API_TOKEN.split(":")[0]

if not botdb.get(db_key):
    initial_data = {
        "users": [],
        "admins": [],
        "banned": []
    }
    botdb.set(db_key, initial_data)

if not ownerID in botdb.get(db_key)["admins"]:
    data = botdb.get(db_key)
    data["admins"].append(ownerID)
    botdb.set(db_key, data)

user_states = {}
user_temp_data = {}
bound_channels = {}
active_roulettes = {}
banned_from_creator_roulettes = {}

ROULETTE_TEXT_PROMPT = (
    "أرسل كليشة السحب\n\n"
    "1 - للتشويش: <code>&lt;tg-spoiler&gt;&lt;/tg-spoiler&gt;</code>\n"
    "<tg-spoiler>مثال</tg-spoiler>\n\n"
    "2 - للتعريض: <code>&lt;b&gt;&lt;/b&gt;</code>\n"
    "<b>مثال</b>\n\n"
    "3 - لجعل النص مائل: <code>&lt;i&gt;&lt;/i&gt;</code>\n"
    "<i>مثال</i>\n\n"
    "4 - للاقتباس: <code>&lt;blockquote&gt;&lt;/blockquote&gt;</code>\n"
    "<blockquote>مثال</blockquote>\n\n"
    "🚫 رجاءً عدم إرسال روابط نهائياً"
)

CHANNEL_BINDING_INSTRUCTIONS = (
    "1️⃣ أضف البوت كمشرف في قناتك.\n"
    "2️⃣ قم بإعادة توجيه أي رسالة من قناتك إلى البوت.\n\n"
    "📌 ملاحظة:\n"
    "جميع المشرفين الآخرين في القناة سيتمكنون أيضًا من استخدام البوت بعد إضافته."
)

CONDITIONAL_CHANNEL_QUESTION = "هل تريد إضافة قناة شرط؟\n\nعند إضافة قناة شرط لن يتمكن أحد من المشاركة في السحب قبل الانضمام لقناة الشرط."
SEND_CONDITIONAL_CHANNEL_LINK = "أرسل رابط القناة الشرطية (مثال: @SSHLA / https://t.me/EGUAKA)"

NOT_YOUR_COMMAND_MSG = "هذا الأمر مخصص لمنشئ الروليت فقط. ❗"

STARTKEY = InlineKeyboardMarkup(row_width=2)
STARTKEY.add(InlineKeyboardButton("إذاعة للمستخدمين", callback_data="broadcast"))
STARTKEY.add(
    InlineKeyboardButton("الاحصائيات", callback_data="stats"),
    InlineKeyboardButton("الأدمنية", callback_data="adminstats"),
)
STARTKEY.add(
    InlineKeyboardButton("المحظورين", callback_data="bannedstats"),
    InlineKeyboardButton("جلب التخزين", callback_data='Get'),
)
STARTKEY.add(
    InlineKeyboardButton("كشف مستخدم", callback_data="whois"),
    InlineKeyboardButton("حظر مستخدم", callback_data="ban"),
)
STARTKEY.add(InlineKeyboardButton("إلغاء الحظر", callback_data="unban"))
STARTKEY.add(
    InlineKeyboardButton("رفع ادمن", callback_data="addadmin"),
    InlineKeyboardButton("تنزيل ادمن", callback_data="remadmin"),
)
def get_user_mention_link(user_id, first_name):
    safe_first_name = (
        first_name
        .replace('[', '\\[')
        .replace(']', '\\]')
        .replace('(', '\\(')
        .replace(')', '\\)')
    )
    return f"[{safe_first_name}](tg://user?id={user_id})"
def main_menu_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎯 إنشاء روليت", callback_data="create_roulette"))
    kb.add(InlineKeyboardButton("🔗 ربط قناة", callback_data="bind_main_channel"),
           InlineKeyboardButton("✖️ فصل القناة", callback_data="disconnect_main_channel"))
    kb.add(InlineKeyboardButton("🔔 ذكرني إذا فزت", callback_data="remind_me_global_info"))
    return kb

def channel_binding_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📥 أضفني إلى قناتك", url=f"https://t.me/{bot.get_me().username}?startchannel=new"),
           InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main_menu"))
    return kb

def roulette_creation_options_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎨 تعديل الكليشة", callback_data="choose_style_instructions"))
    kb.add(InlineKeyboardButton("➕ إضافة قناة شرط", callback_data="prompt_conditional_channel"))
    kb.add(InlineKeyboardButton("⏭️ تخطي", callback_data="skip_conditional_channel"))
    return kb

def conditional_channel_choice_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔗 إضافة رابط قناة", callback_data="send_conditional_channel_link_prompt"))
    kb.add(InlineKeyboardButton("⏭️ تخطي", callback_data="skip_conditional_channel"))
    return kb

def get_channel_roulette_markup(roulette_id: str, is_active: bool):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎁 المشاركة في السحب", callback_data=f"join_roulette_{roulette_id}"))
    kb.add(InlineKeyboardButton("🔔 ذكرني إذا فزت", callback_data=f"remind_me_roulette_{roulette_id}"))
    kb.add(InlineKeyboardButton("▶️ تشغيل المشاركة" if not is_active else "⏸️ إيقاف المشاركة",
                                callback_data=f"toggle_participation_{roulette_id}"),
           InlineKeyboardButton("🏁 ابدأ السحب", callback_data=f"start_draw_{roulette_id}"))
    kb.add(InlineKeyboardButton("📊 عرض المشاركين", callback_data=f"view_participants_{roulette_id}"))
    kb.add(InlineKeyboardButton("❌ حذف الروليت", callback_data=f"delete_roulette_{roulette_id}"))
    kb.add(InlineKeyboardButton("بوت الروليت", url=f"https://t.me/{BOT_USERNAME}"))
 returnkb

def get_user_notification_markup(roulette_id: str, user_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎁 شارك في الروليت", callback_data=f"join_roulette_{roulette_id}"))
    return kb

def get_winner_notification_markup():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎉 تهانينا للفائز!", callback_data="congratulations"))
    return kb

@bot.message_handler(commands=['start'])
def start_cmd(message: Message):
    if message.chat.type != 'private':
        return
        
    user_states.pop(message.from_user.id, None)
    user_temp_data.pop(message.from_user.id, None)

    getDB = botdb.get(db_key)
    user_id = message.from_user.id
    user_first_name = message.from_user.first_name

    current_user_mention = get_user_mention_link(user_id, user_first_name)

    if user_id in getDB["banned"]:
        bot.reply_to(message, "🚫 تم حظرك من استخدام البوت")
        return

    if user_id == ownerID or user_id in getDB["admins"]:
        bot.send_message(message.chat.id, f"""
**• أهلاً بك ⌯ {current_user_mention} .
• أليك لوحة الادمن ..
• يمكنك من خلال اللوحة ان تتحكم بأعدادات البوت والرفع والتنزيل !
**""", reply_markup=STARTKEY, parse_mode='Markdown')
    else:
        bot.send_message(
            message.chat.id,
            "👋 أهلاً بك في بوت الروليت!\nاضغط الزر أدناه لإنشاء روليت:",
            reply_markup=main_menu_kb()
        )

    if not user_id in getDB["users"]:
        data = getDB
        data["users"].append(user_id)
        botdb.set(db_key, data)
        for admin in data["admins"]:
            text = f"– New user stats the bot :"
            username = "@" + message.from_user.username if message.from_user.username else "None"
            text += f"\n\n𖡋 𝐔𝐒𝐄 ⌯  {username}"
            text += f"\n𖡋 𝐍𝐀𝐌𝐄 ⌯  {current_user_mention}" 
            try:
                bot.send_message(admin, text, parse_mode='Markdown')
            except:
                pass

def start_cmd_direct(user, chat_id):
    user_id = user.id
    user_first_name = user.first_name
    
    getDB = botdb.get(db_key)
    current_user_mention = get_user_mention_link(user_id, user_first_name)

    if user_id == ownerID or user_id in getDB["admins"]:
        bot.send_message(chat_id, f"""
**• أهلاً بك ⌯ {current_user_mention} .
• أليك لوحة الادمن ..
• يمكنك من خلال اللوحة ان تتحكم بأعدادات البوت والرفع والتنزيل !
**""", reply_markup=STARTKEY, parse_mode='Markdown')
    else:
        bot.send_message(
            chat_id,
            "👋 أهلاً بك في بوت الروليت!\nاضغط الزر أدناه لإنشاء روليت:",
            reply_markup=main_menu_kb()
        )

@bot.message_handler(commands=['admin'])
def handle_admin_start(message):
    if message.chat.type != 'private':
        return
        
    getDB = botdb.get(db_key)
    user_id = message.from_user.id
    user_first_name = message.from_user.first_name

    current_user_mention = get_user_mention_link(user_id, user_first_name)

    if user_id in getDB["banned"]:
        bot.reply_to(message, "🚫 تم حظرك من استخدام البوت")
        return

    if user_id == ownerID or user_id in getDB["admins"]:
        bot.reply_to(message, f"""
**• أهلاً بك ⌯ {current_user_mention} .
• أليك لوحة الادمن ..
• يمكنك من خلال اللوحة ان تتحكم بأعدادات البوت والرفع والتنزيل !
**""", reply_markup=STARTKEY, parse_mode='Markdown')

    if not user_id in getDB["users"]:
        data = getDB
        data["users"].append(user_id)
        botdb.set(db_key, data)
        for admin in data["admins"]:
            text = f"– New user stats the bot :"
            username = "@" + message.from_user.username if message.from_user.username else "None"
            text += f"\n\n𖡋 𝐔𝐒𝐄 ⌯  {username}"
            text += f"\n𖡋 𝐍𝐀𝐌𝐄 ⌯  {current_user_mention}"
            try:
                bot.send_message(admin, text, parse_mode='Markdown')
            except:
                pass

@bot.callback_query_handler(func=lambda c: c.data == "create_roulette")
def handle_create_roulette_callback(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    if user_id not in bound_channels:
        bot.send_message(call.message.chat.id, "- عليك ربط قناة أولاً قبل إنشاء الروليت. ⚠️\n༄", reply_markup=channel_binding_kb())
        user_states[user_id] = 'awaiting_main_channel_forward'
        return
    
    user_states[user_id] = 'entering_roulette_text'
    bot.send_message(call.message.chat.id, ROULETTE_TEXT_PROMPT, parse_mode='HTML')

@bot.callback_query_handler(func=lambda c: c.data == "bind_main_channel")
def handle_bind_main_channel(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    
    # تأكيد حفظ الحالة
    user_states[user_id] = 'awaiting_main_channel_forward'
    print(f"DEBUG: Set state for user {user_id}: awaiting_main_channel_forward")
    
    bot.send_message(call.message.chat.id, CHANNEL_BINDING_INSTRUCTIONS, reply_markup=channel_binding_kb())

@bot.callback_query_handler(func=lambda c: c.data == "disconnect_main_channel")
def handle_disconnect_main_channel(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    
    if user_id in bound_channels:
        del bound_channels[user_id]
        if user_id in active_roulettes:
            del active_roulettes[user_id]
        bot.send_message(call.message.chat.id, "تم فصل القناة بنجاح. ✅")
    else:
        bot.send_message(call.message.chat.id, "لم تقم بربط أي قناة بعد.❗")

@bot.callback_query_handler(func=lambda c: c.data == "back_to_main_menu")
def handle_back_to_main_menu(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    user_states.pop(user_id, None)
    user_temp_data.pop(user_id, None)
    bot.send_message(
        call.message.chat.id,
        "👋 أهلاً بك في بوت الروليت!\nاضغط الزر أدناه لإنشاء روليت:",
        reply_markup=main_menu_kb()
    )

@bot.callback_query_handler(func=lambda c: c.data == "remind_me_global_info")
def handle_remind_me_global_info(call):
    bot.answer_callback_query(call.id, "للتذكير، يجب عليك تفعيل زر التذكير لكل سحب على حدة في رسالة السحب. هذا الزر يعرض معلومات فقط.!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "choose_style_instructions")
def handle_choose_style_instructions(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    user_states[user_id] = 'entering_roulette_text'
    bot.send_message(call.message.chat.id, ROULETTE_TEXT_PROMPT, parse_mode='HTML')

@bot.callback_query_handler(func=lambda c: c.data == "prompt_conditional_channel")
def handle_prompt_conditional_channel(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, CONDITIONAL_CHANNEL_QUESTION, reply_markup=conditional_channel_choice_kb())

@bot.callback_query_handler(func=lambda c: c.data == "send_conditional_channel_link_prompt")
def handle_send_conditional_channel_link_prompt(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    
    # تأكيد حفظ الحالة
    user_states[user_id] = 'entering_conditional_channel_link'
    print(f"DEBUG: Set state for user {user_id}: entering_conditional_channel_link")
    
    bot.send_message(call.message.chat.id, SEND_CONDITIONAL_CHANNEL_LINK)

@bot.callback_query_handler(func=lambda c: c.data == "skip_conditional_channel")
def handle_skip_conditional_channel(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)
    
    if user_id not in user_temp_data:
        bot.send_message(call.message.chat.id, "يرجى إنشاء الروليت أولاً. ❗")
        return
    
    roulette_data = user_temp_data[user_id]
    roulette_id = str(uuid.uuid4())
    
    active_roulettes[user_id] = {
        'id': roulette_id,
        'text': roulette_data['text'],
        'participants': [],
        'is_active': True,
        'channel_id': bound_channels[user_id]['channel_id'],
        'conditional_channel': None
    }
    
    try:
        sent_message = bot.send_message(
            bound_channels[user_id]['channel_id'],
            roulette_data['text'],
            reply_markup=get_channel_roulette_markup(roulette_id, True),
            parse_mode='HTML'
        )
        active_roulettes[user_id]['message_id'] = sent_message.message_id
        bot.send_message(call.message.chat.id, "✅ تم إنشاء الروليت بنجاح!")
        user_temp_data.pop(user_id, None)
        user_states.pop(user_id, None)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ فشل في إرسال الروليت: {str(e)}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("join_roulette_"))
def handle_join_roulette(call):
    roulette_id = call.data.split("_")[2]
    user_id = call.from_user.id
    
    creator_id = None
    for uid, roulette in active_roulettes.items():
        if roulette['id'] == roulette_id:
            creator_id = uid
            break
    
    if not creator_id:
        bot.answer_callback_query(call.id, "❌ الروليت غير موجود أو منتهي الصلاحية.")
        return
    
    roulette = active_roulettes[creator_id]
    
    if not roulette['is_active']:
        bot.answer_callback_query(call.id, "❌ المشاركة في هذا الروليت متوقفة حالياً.")
        return
    
    if user_id in banned_from_creator_roulettes.get(creator_id, []):
        bot.answer_callback_query(call.id, "❌ أنت محظور من المشاركة في هذا الروليت.")
        return
    
    if roulette['conditional_channel']:
        try:
            member = bot.get_chat_member(roulette['conditional_channel']['id'], user_id)
            if member.status in ['left', 'kicked']:
                conditional_kb = InlineKeyboardMarkup()
                conditional_kb.add(InlineKeyboardButton("🔗 انضم للقناة", url=roulette['conditional_channel']['url']))
                bot.answer_callback_query(call.id, f"يجب عليك الانضمام لقناة {roulette['conditional_channel']['name']} أولاً!")
                return
        except:
            conditional_kb = InlineKeyboardMarkup()
            conditional_kb.add(InlineKeyboardButton("🔗 انضم للقناة", url=roulette['conditional_channel']['url']))
            bot.answer_callback_query(call.id, f"يجب عليك الانضمام لقناة {roulette['conditional_channel']['name']} أولاً!")
            return
    
    if user_id in [p['user_id'] for p in roulette['participants']]:
        bot.answer_callback_query(call.id, "❌ أنت مشارك بالفعل في هذا الروليت.")
        return
    
    participant = {
        'user_id': user_id,
        'first_name': call.from_user.first_name,
        'username': call.from_user.username
    }
    roulette['participants'].append(participant)
    
    bot.answer_callback_query(call.id, f"✅ تم تسجيلك في الروليت! (المشاركين: {len(roulette['participants'])})")
    
    try:
        updated_markup = get_channel_roulette_markup(roulette_id, roulette['is_active'])
        bot.edit_message_reply_markup(
            chat_id=roulette['channel_id'],
            message_id=roulette['message_id'],
            reply_markup=updated_markup
        )
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("remind_me_roulette_"))
def handle_remind_me_roulette(call):
    roulette_id = call.data.split("_")[3]
    user_id = call.from_user.id
    
    creator_id = None
    for uid, roulette in active_roulettes.items():
        if roulette['id'] == roulette_id:
            creator_id = uid
            break
    
    if not creator_id:
        bot.answer_callback_query(call.id, "❌ الروليت غير موجود أو منتهي الصلاحية.")
        return
    
    notification_key = f"notify_{creator_id}_{roulette_id}"
    current_notifications = botdb.get(notification_key) or []
    
    if user_id not in current_notifications:
        current_notifications.append(user_id)
        botdb.set(notification_key, current_notifications)
        bot.answer_callback_query(call.id, "🔔 سيتم إشعارك عند اختيار الفائز!")
    else:
        bot.answer_callback_query(call.id, "✅ أنت مسجل بالفعل للحصول على الإشعارات.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("toggle_participation_"))
def handle_toggle_participation(call):
    roulette_id = call.data.split("_")[2]
    user_id = call.from_user.id
    
    if user_id not in active_roulettes or active_roulettes[user_id]['id'] != roulette_id:
        bot.answer_callback_query(call.id, NOT_YOUR_COMMAND_MSG)
        return
    
    roulette = active_roulettes[user_id]
    roulette['is_active'] = not roulette['is_active']
    
    status = "تم تشغيل" if roulette['is_active'] else "تم إيقاف"
    bot.answer_callback_query(call.id, f"✅ {status} المشاركة في الروليت.")
    
    try:
        updated_markup = get_channel_roulette_markup(roulette_id, roulette['is_active'])
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=updated_markup
        )
    except Exception as e:
        print(f"Error updating message markup: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("start_draw_"))
def handle_start_draw(call):
    roulette_id = call.data.split("_")[2]
    user_id = call.from_user.id
    
    if user_id not in active_roulettes or active_roulettes[user_id]['id'] != roulette_id:
        bot.answer_callback_query(call.id, NOT_YOUR_COMMAND_MSG)
        return
    
    roulette = active_roulettes[user_id]
    
    if len(roulette['participants']) == 0:
        bot.answer_callback_query(call.id, "❌ لا يوجد مشاركين في الروليت.")
        return
    
    winner = random.choice(roulette['participants'])
    winner_mention = get_user_mention_link(winner['user_id'], winner['first_name'])
    
    result_text = f"""
🎉 **تم اختيار الفائز!**

🏆 الفائز: {winner_mention}
 @eAOQ_BoT 👥 عدد المشاركين: {len(roulette['participants'])}
    """
    
    try:
        bot.edit_message_text(
            text=result_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=get_winner_notification_markup(),
            parse_mode='Markdown'
        )
    except:
        bot.send_message(call.message.chat.id, result_text, parse_mode='Markdown')
    
    notification_key = f"notify_{user_id}_{roulette_id}"
    notifications = botdb.get(notification_key) or []
    
    for notify_user_id in notifications:
        try:
            notification_text = f"""
🔔 **إشعار الروليت**

🎉 تم اختيار الفائز في الروليت!
🏆 الفائز: {winner_mention}

انقر الزر أدناه للذهاب إلى الروليت.
            """
            bot.send_message(
                notify_user_id,
                notification_text,
                reply_markup=get_user_notification_markup(roulette_id, notify_user_id),
                parse_mode='Markdown'
            )
        except:
            pass
    
    botdb.delete(notification_key)
    bot.answer_callback_query(call.id, f"🎉 تم اختيار الفائز: {winner['first_name']}")
    del active_roulettes[user_id]

@bot.callback_query_handler(func=lambda c: c.data.startswith("view_participants_"))
def handle_view_participants(call):
    roulette_id = call.data.split("_")[2]
    user_id = call.from_user.id
    
    if user_id not in active_roulettes or active_roulettes[user_id]['id'] != roulette_id:
        bot.answer_callback_query(call.id, NOT_YOUR_COMMAND_MSG)
        return
    
    roulette = active_roulettes[user_id]
    participants = roulette['participants']
    
    if not participants:
        bot.answer_callback_query(call.id, "❌ لا يوجد مشاركين حتى الآن.")
        return
    
    participants_text = f"👥 **المشاركين في الروليت** ({len(participants)}):\n\n"
    
    for i, participant in enumerate(participants, 1):
        user_mention = get_user_mention_link(participant['user_id'], participant['first_name'])
        participants_text += f"{i}. {user_mention}\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📊 تحديث القائمة", callback_data=f"view_participants_{roulette_id}"))
    kb.add(InlineKeyboardButton("🚫 حظر مستخدم", callback_data=f"ban_user_{roulette_id}"))
    
    bot.send_message(call.message.chat.id, participants_text, reply_markup=kb, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("delete_roulette_"))
def handle_delete_roulette(call):
    roulette_id = call.data.split("_")[2]
    user_id = call.from_user.id
    
    if user_id not in active_roulettes or active_roulettes[user_id]['id'] != roulette_id:
        bot.answer_callback_query(call.id, NOT_YOUR_COMMAND_MSG)
        return
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        bot.edit_message_text("❌ تم حذف الروليت", call.message.chat.id, call.message.message_id)
    
    notification_key = f"notify_{user_id}_{roulette_id}"
    botdb.delete(notification_key)
    
    del active_roulettes[user_id]
    bot.answer_callback_query(call.id, "✅ تم حذف الروليت بنجاح.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("ban_user_"))
def handle_ban_user_from_roulette(call):
    roulette_id = call.data.split("_")[2]
    user_id = call.from_user.id
    
    if user_id not in active_roulettes or active_roulettes[user_id]['id'] != roulette_id:
        bot.answer_callback_query(call.id, NOT_YOUR_COMMAND_MSG)
        return
    
    user_states[user_id] = f'banning_user_{roulette_id}'
    bot.send_message(call.message.chat.id, "أرسل ID المستخدم الذي تريد حظره من الروليت:")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "congratulations")
def handle_congratulations(call):
    bot.answer_callback_query(call.id, "🎉 تهانينا للفائز! 🎊")

@bot.message_handler(content_types=['text', 'audio', 'photo', 'video', 'document'], func=lambda message: True)
def handle_messages_by_state(message: Message):
    user_id = message.from_user.id
    current_state = user_states.get(user_id)

    if current_state == 'awaiting_main_channel_forward':
        if message.forward_from_chat and message.forward_from_chat.type == "channel":
            channel = message.forward_from_chat
            try:
                bot_member = bot.get_chat_member(channel.id, bot.get_me().id)
                if bot_member.status not in ['administrator', 'creator']:
                    bot.send_message(message.chat.id, "❗ البوت ليس مشرفاً في هذه القناة. الرجاء إضافة البوت كمشرف وإعادة التوجيه.")
                    return
            except Exception:
                bot.send_message(message.chat.id, "❗ حدث خطأ أثناء التحقق من صلاحيات البوت في القناة. تأكد من أن القناة عامة وأن البوت مشرف.")
                return

            bound_channels[user_id] = {
                'channel_id': channel.id,
                'channel_username': channel.username
            }
            bot.send_message(message.chat.id, f"✅ تم ربط القناة: @{channel.username or channel.title}")
            user_states.pop(user_id, None)
        else:
            bot.send_message(message.chat.id, "❗ يرجى إعادة توجيه رسالة من قناة عامة أضفت فيها البوت كمشرف.")

    elif current_state == 'entering_roulette_text':
        if re.search(r'http[s]?://|t\.me/|@', message.text):
            bot.reply_to(message, "🚫 لا يُسمح بالروابط في نص الروليت.\nأرسل النص مرة أخرى بدون روابط.")
            return
        
        user_temp_data[user_id] = {'text': message.text}
        user_states[user_id] = 'roulette_options'
        bot.send_message(message.chat.id, "✅ تم حفظ النص.\nاختر إجراء:", reply_markup=roulette_creation_options_kb())
    
    elif current_state == 'entering_conditional_channel_link':
        channel_url = message.text.strip()
        
        if not (channel_url.startswith('@') or 'https://t.me/' in channel_url):
            bot.reply_to(message, "❌ الرابط غير صحيح. يجب أن يبدأ بـ @ أو https://t.me/")
            return
        
        channel_username = None
        if channel_url.startswith('@'):
            channel_username = channel_url[1:]
        elif 'https://t.me/' in channel_url:
            channel_username = channel_url.split('/')[-1]
        
        if not channel_username:
            bot.reply_to(message, "❌ لم يتم العثور على اسم المستخدم للقناة.")
            return
        
        try:
            channel_info = bot.get_chat(f"@{channel_username}")
            conditional_channel = {
                'id': channel_info.id,
                'name': f"@{channel_username}",
                'url': f"https://t.me/{channel_username}"
            }
            
            if user_id not in user_temp_data:
                bot.reply_to(message, "يرجى إنشاء الروليت أولاً. ❗")
                return
            
            roulette_data = user_temp_data[user_id]
            roulette_id = str(uuid.uuid4())
            
            active_roulettes[user_id] = {
                'id': roulette_id,
                'text': roulette_data['text'],
                'participants': [],
                'is_active': True,
                'channel_id': bound_channels[user_id]['channel_id'],
                'conditional_channel': conditional_channel
            }
            
            try:
                sent_message = bot.send_message(
                    bound_channels[user_id]['channel_id'],
                    roulette_data['text'],
                    reply_markup=get_channel_roulette_markup(roulette_id, True),
                    parse_mode='HTML'
                )
                active_roulettes[user_id]['message_id'] = sent_message.message_id
                bot.send_message(message.chat.id, f"✅ تم إنشاء الروليت بنجاح مع قناة الشرط: {conditional_channel['name']}")
                user_temp_data.pop(user_id, None)
                user_states.pop(user_id, None)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ فشل في إرسال الروليت: {str(e)}")
                
        except Exception as e:
            bot.reply_to(message, f"❌ خطأ في التحقق من القناة: {str(e)}")
    
    elif current_state and current_state.startswith('banning_user_'):
        roulette_id = current_state.split('_')[2]
        try:
            ban_user_id = int(message.text)
            
            if user_id not in banned_from_creator_roulettes:
                banned_from_creator_roulettes[user_id] = []
            
            if ban_user_id not in banned_from_creator_roulettes[user_id]:
                banned_from_creator_roulettes[user_id].append(ban_user_id)
                
                roulette = active_roulettes[user_id]
                roulette['participants'] = [p for p in roulette['participants'] if p['user_id'] != ban_user_id]
                
                bot.reply_to(message, f"✅ تم حظر المستخدم {ban_user_id} من هذا الروليت وإزالته من المشاركين.")
            else:
                bot.reply_to(message, "المستخدم محظور مسبقاً من هذا الروليت.")
            
            user_states.pop(user_id, None)
        except ValueError:
            bot.reply_to(message, "❌ يرجى إرسال ID صحيح.")
    
    # معالجة الرسائل النصية العادية للوحة الإدارة
    elif message.content_type == 'text':
        handle_regular_text_messages(message)
    
    elif not message.text or not message.text.startswith('/'):
        bot.send_message(message.chat.id, "❗ أمر غير مفهوم. الرجاء استخدام الأزرار أو /start للبدء.", reply_markup=main_menu_kb())

def handle_regular_text_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    if message.chat.type != 'private':
        return
    
    print(f"DEBUG: Processing regular text message from user {user_id}")
    print(f"DEBUG: Text: {text}")
    
    getDB = botdb.get(db_key)
    user_first_name = message.from_user.first_name
    current_user_mention = get_user_mention_link(user_id, user_first_name)
    is_admin = user_id == ownerID or user_id in getDB["admins"]
    
    if text == "الغاء":
        bot.reply_to(message, "تم إلغاء العملية ✅", reply_markup=STARTKEY)
        return

    if botdb.get(f"broad:{user_id}") and is_admin:
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")
        
        users = getDB["users"]
        success_count = 0
        for target_user in users:
            try:
                bot.send_message(target_user, text, parse_mode='Markdown')
                success_count += 1
                time.sleep(0.05)
            except:
                pass
        
        bot.reply_to(message, f"تم ارسال الرسالة الى {success_count} مستخدم", reply_markup=STARTKEY)
        return

    if botdb.get(f"whois:{user_id}") and is_admin:
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")
        
        try:
            user_info = bot.get_chat(text)
            user_mention = get_user_mention_link(user_info.id, user_info.first_name)
            response = f"""
معلومات المستخدم:
الاسم: {user_mention}
الايدي: `{user_info.id}`
اليوزر: @{user_info.username if user_info.username else 'لا يوجد'}
            """
            bot.reply_to(message, response, reply_markup=STARTKEY, parse_mode='Markdown')
        except:
            bot.reply_to(message, "المستخدم غير موجود", reply_markup=STARTKEY)
        return
# تم تصحيح الاخطاء Roman
#BY @S5BB5 - @ABYWQ

    if botdb.get(f"ban:{user_id}") and is_admin:
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")
        
        try:
            target_id = int(text)
            data = getDB
            if target_id not in data["banned"]:
                data["banned"].append(target_id)
                botdb.set(db_key, data)
                bot.reply_to(message, "تم حظر المستخدم ✅", reply_markup=STARTKEY)
            else:
                bot.reply_to(message, "المستخدم محظور مسبقاً", reply_markup=STARTKEY)
        except:
            bot.reply_to(message, "ايدي غير صحيح", reply_markup=STARTKEY)
        return

    if botdb.get(f"unban:{user_id}") and is_admin:
        botdb.delete(f"unban:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")
        
        try:
            target_id = int(text)
            data = getDB
            if target_id in data["banned"]:
                data["banned"].remove(target_id)
                botdb.set(db_key, data)
                bot.reply_to(message, "تم إلغاء الحظر ✅", reply_markup=STARTKEY)
            else:
                bot.reply_to(message, "المستخدم غير محظور", reply_markup=STARTKEY)
        except:
            bot.reply_to(message, "ايدي غير صحيح", reply_markup=STARTKEY)
        return

    if botdb.get(f"add:{user_id}") and is_admin:
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")
        
        try:
            target_id = int(text)
            data = getDB
            if target_id not in data["admins"]:
                data["admins"].append(target_id)
                botdb.set(db_key, data)
                bot.reply_to(message, "تم رفع المستخدم ادمن ✅", reply_markup=STARTKEY)
            else:
                bot.reply_to(message, "المستخدم ادمن مسبقاً", reply_markup=STARTKEY)
        except:
            bot.reply_to(message, "ايدي غير صحيح", reply_markup=STARTKEY)
        return

    if botdb.get(f"rem:{user_id}") and is_admin:
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"unban:{user_id}")
        
        try:
            target_id = int(text)
            if target_id == ownerID:
                bot.reply_to(message, "لا يمكن تنزيل المالك", reply_markup=STARTKEY)
                return
            data = getDB
            if target_id in data["admins"]:
                data["admins"].remove(target_id)
                botdb.set(db_key, data)
                bot.reply_to(message, "تم تنزيل المستخدم من الإدارة ✅", reply_markup=STARTKEY)
            else:
                bot.reply_to(message, "المستخدم ليس ادمن", reply_markup=STARTKEY)
        except:
            bot.reply_to(message, "ايدي غير صحيح", reply_markup=STARTKEY)
        return

    state = user_states.get(user_id)
    
    if state == 'entering_roulette_text':
        if re.search(r'http[s]?://|t\.me/|@', text):
            bot.reply_to(message, "🚫 لا يُسمح بالروابط في نص الروليت.\nأرسل النص مرة أخرى بدون روابط.")
            return
        
        user_temp_data[user_id] = {'text': text}
        user_states[user_id] = 'roulette_options'
        bot.send_message(message.chat.id, "✅ تم حفظ النص.\nاختر إجراء:", reply_markup=roulette_creation_options_kb())
    
    elif state == 'entering_conditional_channel_link':
        channel_url = text.strip()
        
        if not (channel_url.startswith('@') or 'https://t.me/' in channel_url):
            bot.reply_to(message, "❌ الرابط غير صحيح. يجب أن يبدأ بـ @ أو https://t.me/")
            return
        
        channel_username = None
        if channel_url.startswith('@'):
            channel_username = channel_url[1:]
        elif 'https://t.me/' in channel_url:
            channel_username = channel_url.split('/')[-1]
        
        if not channel_username:
            bot.reply_to(message, "❌ لم يتم العثور على اسم المستخدم للقناة.")
            return
        
        try:
            channel_info = bot.get_chat(f"@{channel_username}")
            conditional_channel = {
                'id': channel_info.id,
                'name': f"@{channel_username}",
                'url': f"https://t.me/{channel_username}"
            }
            
            if user_id not in user_temp_data:
                bot.reply_to(message, "يرجى إنشاء الروليت أولاً. ❗")
                return
            
            roulette_data = user_temp_data[user_id]
            roulette_id = str(uuid.uuid4())
            
            active_roulettes[user_id] = {
                'id': roulette_id,
                'text': roulette_data['text'],
                'participants': [],
                'is_active': True,
                'channel_id': bound_channels[user_id]['channel_id'],
                'conditional_channel': conditional_channel
            }
            
            try:
                sent_message = bot.send_message(
                    bound_channels[user_id]['channel_id'],
                    roulette_data['text'],
                    reply_markup=get_channel_roulette_markup(roulette_id, True),
                    parse_mode='HTML'
                )
                active_roulettes[user_id]['message_id'] = sent_message.message_id
                bot.send_message(message.chat.id, f"✅ تم إنشاء الروليت بنجاح مع قناة الشرط: {conditional_channel['name']}")
                user_temp_data.pop(user_id, None)
                user_states.pop(user_id, None)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ فشل في إرسال الروليت: {str(e)}")
                
        except Exception as e:
            bot.reply_to(message, f"❌ خطأ في التحقق من القناة: {str(e)}")
    
    elif state and state.startswith('banning_user_'):
        roulette_id = state.split('_')[2]
        try:
            ban_user_id = int(text)
            
            if user_id not in banned_from_creator_roulettes:
                banned_from_creator_roulettes[user_id] = []
            
            if ban_user_id not in banned_from_creator_roulettes[user_id]:
                banned_from_creator_roulettes[user_id].append(ban_user_id)
                
                roulette = active_roulettes[user_id]
                roulette['participants'] = [p for p in roulette['participants'] if p['user_id'] != ban_user_id]
                
                bot.reply_to(message, f"✅ تم حظر المستخدم {ban_user_id} من هذا الروليت وإزالته من المشاركين.")
            else:
                bot.reply_to(message, "المستخدم محظور مسبقاً من هذا الروليت.")
            
            user_states.pop(user_id, None)
        except ValueError:
            bot.reply_to(message, "❌ يرجى إرسال ID صحيح.")



@bot.callback_query_handler(func=lambda call: True)
def callback_query_handler(call):
    user_id = call.from_user.id
    is_admin = user_id == ownerID or user_id in botdb.get(db_key)["admins"]
    getDB = botdb.get(db_key)
    user_first_name = call.from_user.first_name
    current_user_mention = get_user_mention_link(user_id, user_first_name)

    if call.data == "back" and is_admin:
        bot.edit_message_text(f"""
**• أهلاً بك ⌯ {current_user_mention} .
• أليك لوحة الادمن ..
• يمكنك من خلال اللوحة ان تتحكم بأعدادات البوت والرفع والتنزيل !
**""", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=STARTKEY, parse_mode='Markdown')

        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")

    elif call.data == "addadmin" and is_admin:
        bot.edit_message_text("• ارسل الآن ايدي المستخدم لرفعه ادمن\n• للإلغاء ارسل الغاء ", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")))
        botdb.set(f"add:{user_id}", True)
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")
        
    elif call.data == "remadmin" and is_admin:
        bot.edit_message_text("• ارسل الآن ايدي المستخدم لتنزيله من الإدارة\n• للإلغاء ارسل الغاء ", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")))
        botdb.set(f"rem:{user_id}", True)
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"unban:{user_id}")
        

    elif call.data == "broadcast" and is_admin:
        bot.edit_message_text("• ارسل الان الرسالة المراد اذاعتها\n• يمكنك ارسال صور مع التعليق عليها\n• للإلغاء ارسل الغاء ", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")))
        botdb.set(f"broad:{user_id}", True)
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"unban:{user_id}")

    elif call.data == "stats" and is_admin:
        users = len(getDB["users"])
        admins = len(getDB["admins"])
        banned = len(getDB["banned"])
        bot.edit_message_text(f"""
📊 **احصائيات البوت**

👥 المستخدمين: `{users}`
👨‍💼 الأدمنية: `{admins}`
🚫 المحظورين: `{banned}`
""", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")), parse_mode='Markdown')

    elif call.data == "adminstats" and is_admin:
        admins = getDB["admins"]
        admin_list = ""
        for admin_id in admins:
            try:
                admin_info = bot.get_chat(admin_id)
                admin_mention = get_user_mention_link(admin_id, admin_info.first_name)
                admin_list += f"• {admin_mention}\n"
            except:
                admin_list += f"• `{admin_id}` (غير متاح)\n"
        
        bot.edit_message_text(f"""
👨‍💼 **قائمة الأدمنية**

{admin_list}
""", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")), parse_mode='Markdown')

    elif call.data == "bannedstats" and is_admin:
        banned = getDB["banned"]
        if not banned:
            banned_list = "لا يوجد مستخدمين محظورين"
        else:
            banned_list = ""
            for banned_id in banned:
                try:
                    banned_info = bot.get_chat(banned_id)
                    banned_mention = get_user_mention_link(banned_id, banned_info.first_name)
                    banned_list += f"• {banned_mention}\n"
                except:
                    banned_list += f"• `{banned_id}` (غير متاح)\n"
        
        bot.edit_message_text(f"""
🚫 **قائمة المحظورين**

{banned_list}
""", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")), parse_mode='Markdown')

    elif call.data == "whois" and is_admin:
        bot.edit_message_text("• ارسل الآن ايدي المستخدم او يوزرنيمه\n• للإلغاء ارسل الغاء ", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")))
        botdb.set(f"whois:{user_id}", True)
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")
# تم تصحيح الاخطاء Roman
#BY @S5BB5 - @ABYWQ

    elif call.data == "ban" and is_admin:
        bot.edit_message_text("• ارسل الآن ايدي المستخدم لحظره\n• للإلغاء ارسل الغاء ", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")))
        botdb.set(f"ban:{user_id}", True)
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")
        botdb.delete(f"unban:{user_id}")

    elif call.data == "unban" and is_admin:
        bot.edit_message_text("• ارسل الآن ايدي المستخدم لإلغاء حظره\n• للإلغاء ارسل الغاء ", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("رجوع", callback_data="back")))
        botdb.set(f"unban:{user_id}", True)
        botdb.delete(f"whois:{user_id}")
        botdb.delete(f"broad:{user_id}")
        botdb.delete(f"ban:{user_id}")
        botdb.delete(f"add:{user_id}")
        botdb.delete(f"rem:{user_id}")

    elif call.data == "Get" and is_admin:
        try:
            with open('database.db', 'rb') as db_file:
                bot.send_document(call.message.chat.id, db_file, caption="📁 ملف قاعدة البيانات")
        except Exception as e:
            bot.answer_callback_query(call.id, f"خطأ في جلب الملف: {str(e)}", show_alert=True)

print("تم تشغيل البوت بنجاح... ✅")
bot.infinity_polling()
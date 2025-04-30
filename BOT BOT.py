import telebot
import requests
import json
import io
import time
import logging
import random
import re
import threading
import pickle
import os
import hashlib
from random import randint
from functools import lru_cache
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from langdetect import detect

# ========== إعدادات البوت الأساسية ==========
BOT_TOKEN = '7869585333:AAFijfzS6uGT6farjDqk1Li8-pmOQJaTJwY'
UUID = '3eaa425e-09a2-41e8-9334-aa8db190e546'
IDADMIN = 7038758847  # ID المطور
bot = telebot.TeleBot(BOT_TOKEN)

# ========== متغيرات البوت ==========
user_sessions = {}
last_used_time = {}
user_ratings = {}
blocked_users = set()
admins = {IDADMIN}
chat_logs = {}
captcha_data = {}
new_user_warnings = {}
flood_count = {}
FLOOD_SECONDS = 3
MAX_ATTEMPTS = 3
start_time = datetime.now()
MAX_PROJECTS_PER_USER = 80  # الحد الأقصى للمشاريع لكل مستخدم
VIP_CODES = {}  # تخزين أكواد VIP
USER_POINTS = {}  # نقاط المستخدمين
VIP_USERS = {}  # مستخدمين VIP وتاريخ انتهاء العضوية
DAILY_GIFT_COOLDOWN = {}  # تبريد الهدايا اليومية
ADMIN_ACTIONS = {}  # إجراءات الأدمن

# ========== نظام الرتب والتحليلات ==========
user_ranks = {
    "مبتدئ": 0,
    "مطور": 3,
    "مستشار": 10,
    "عبقري": 20,
    "مهندس": 25,
    "مبرمج حسابي": 30,
    "مدمن البوت": 35,
    "سجاج البوت": 40,
    "مختم البوت": 45,
    "يحتار عن تكلم عنه": 50,
    "VIP": 55  # الرتبة الأخيرة
}

# نقاط لكل رتبة
RANK_POINTS = {
    "مبتدئ": 0,
    "مطور": 10,
    "مستشار": 20,
    "عبقري": 30,
    "مهندس": 40,
    "مبرمج حسابي": 50,
    "مدمن البوت": 60,
    "سجاج البوت": 70,
    "مختم البوت": 80,
    "يحتار عن تكلم عنه": 90,
    "VIP": 100
}

user_analytics = {}
CURRENT_VERSION = "1.0"
battle_requests = {}

# ========== إعدادات الأمان ==========
MAX_REQUESTS_PER_MINUTE = 10
ANTI_SPAM_TIME = 2
MAX_MESSAGE_LENGTH = 500
BLACKLIST_WORDS = ["بورن", "إباحي", "hack", "قرصنة"]
BACKUP_FILE = 'bot_backup.pkl'

# ========== إعدادات الواجهة ==========
WELCOME_IMAGE_URL = "https://t.me/VXRCAHT/28472"
DECOR = "><™~°¶§~•°™><"
RULES_LINK = "@VXRVIP"

# ========== شخصية البوت ==========
PERSONALITY_RESPONSES = [
    "🔥 راح يعجبك التصميم الجاي!",
    "⏳ ثواني وراح أنطيك شي ناري...",
    "🤔 إنت تستاهل أفضل من كذا...",
    "💡 عندي فكرة رهيبة لتعديل مشروعك!"
]

# ========== رسائل تشجيعية ==========
encouragement = [
    "🔥 إبداع! جرب فكرة أخرى",
    "🚀 ممتاز! هل تريد إضافة مميزات أخرى؟",
    "💡 يمكنك إرسال /example لرؤية أفكار جاهزة",
    "✨ رائع! ماذا تريد أن تصنع بعد؟"
]

# ========== إعداد نظام التسجيل ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# ========== الدوال المساعدة ==========
def log_activity(user_id, action):
    try:
        user = bot.get_chat(user_id)
        logging.info(f"User @{user.username} ({user_id}): {action}")
    except:
        logging.info(f"User {user_id}: {action}")

def detect_lang(text):
    try:
        return 'ar' if detect(text) == 'ar' else 'en'
    except:
        return 'en'

def is_arabic(text):
    return any('\u0600' <= c <= '\u06FF' for c in text)

def is_user_allowed(user_id):
    return (user_id not in blocked_users and 
            (user_id not in last_used_time or 
             time.time() - last_used_time[user_id] > FLOOD_SECONDS))

def generate_captcha():
    num1 = randint(1, 10)
    num2 = randint(1, 10)
    return num1, num2, num1 + num2

def send_admin_notification(text):
    try:
        bot.send_message(IDADMIN, f"🔔 إشعار نظام:\n{text}")
    except:
        logging.error("Failed to send admin notification")

def contains_blacklist_words(text):
    text_lower = text.lower()
    return any(word in text_lower for word in BLACKLIST_WORDS)

def is_potential_attack(text):
    sql_keywords = ["SELECT", "INSERT", "DELETE", "UPDATE", "DROP", "--"]
    return any(keyword in text.upper() for keyword in sql_keywords)

def get_personality_response():
    return random.choice(PERSONALITY_RESPONSES)

def update_rank(user_id):
    projects_count = user_analytics.get(user_id, {}).get("generated_apps", 0)
    new_rank = "مبتدئ"
    for rank, limit in user_ranks.items():
        if projects_count >= limit:
            new_rank = rank
    
    if new_rank != user_analytics.get(user_id, {}).get("rank"):
        points_reward = RANK_POINTS.get(new_rank, 0)
        USER_POINTS[user_id] = USER_POINTS.get(user_id, 0) + points_reward
        
        bot.send_message(user_id, f"""
🎖️ ترقيتك إلى رتبة: {new_rank}!
📊 عدد مشاريعك: {projects_count}
💰 حصلت على {points_reward} نقطة كمكافأة!
""")
        user_analytics[user_id]["rank"] = new_rank
        
        # إذا وصل إلى رتبة VIP
        if new_rank == "VIP":
            vip_code = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:8].upper()
            VIP_CODES[vip_code] = {
                'user_id': user_id,
                'expiry': time.time() + 86400  # يوم واحد
            }
            bot.send_message(user_id, f"""
🎊 مبروك! لقد وصلت إلى رتبة VIP!
🔑 كود VIP الخاص بك: {vip_code}
📅 تنتهي العضوية بعد 24 ساعة

استخدم الأمر /vip ثم اختر "التحقق من كود VIP" لتفعيل العضوية
""")

def ai_suggestions(user_id, project_type):
    suggestions = {
        "متجر": ["🛒 أضف صفحة تسجيل دخول؟", "⭐ أضف تقييمات المنتجات؟"],
        "موقع": ["🎨 تريد ستايل احترافي؟", "✍️ أضف مدونة؟"],
        "أداة": ["📹 أضف شرح فيديو؟", "📱 أضف زر مشاركة؟"]
    }
    markup = InlineKeyboardMarkup()
    for suggestion in suggestions.get(project_type, []):
        markup.add(InlineKeyboardButton(suggestion, callback_data=f"sugg_{suggestion[:5]}"))
    bot.send_message(user_id, "🔮 هل تريد تحسينات إضافية؟", reply_markup=markup)

def save_backup():
    data = {
        'user_sessions': user_sessions,
        'user_ratings': user_ratings,
        'blocked_users': list(blocked_users),
        'user_analytics': user_analytics,
        'USER_POINTS': USER_POINTS,
        'VIP_CODES': VIP_CODES,
        'VIP_USERS': VIP_USERS,
        'DAILY_GIFT_COOLDOWN': DAILY_GIFT_COOLDOWN
    }
    with open(BACKUP_FILE, 'wb') as f:
        pickle.dump(data, f)

def load_backup():
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, 'rb') as f:
            data = pickle.load(f)
            globals().update(data)

# ========== نظام التحقق (CAPTCHA) ==========
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if user_id in blocked_users:
        bot.send_message(message.chat.id, "❌ أنت محظور! يمكنك فقط استخدام أمر /contact للتواصل مع المطور")
        return
    
    num1, num2, answer = generate_captcha()
    captcha_data[user_id] = {
        'answer': answer,
        'attempts': 0,
        'last_attempt': time.time()
    }
    
    captcha_msg = f"""
{DECOR}
🔐 للتحقق من أنك لست روبوت، حل المسألة:
{num1} + {num2} = ؟
لديك 10 محاولات فقط!
{DECOR}
    """
    bot.send_message(message.chat.id, captcha_msg)
    log_activity(user_id, "Started CAPTCHA")

@bot.message_handler(func=lambda m: m.from_user.id in captcha_data)
def verify_captcha(message):
    user_id = message.from_user.id
    captcha_info = captcha_data.get(user_id)
    
    # التحقق من التوقيت بين المحاولات
    if time.time() - captcha_info['last_attempt'] < 5:
        bot.send_message(message.chat.id, "⏳ انتظر 5 ثواني بين كل محاولة")
        return
    
    captcha_info['last_attempt'] = time.time()
    
    try:
        if int(message.text) == captcha_info['answer']:
            del captcha_data[user_id]
            send_real_welcome(message)
            log_activity(user_id, "Passed CAPTCHA")
        else:
            captcha_info['attempts'] += 1
            remaining_attempts = 10 - captcha_info['attempts']
            
            if captcha_info['attempts'] >= 10:
                blocked_users.add(user_id)
                bot.send_message(message.chat.id, "❌ تم حظرك بسبب تجاوز عدد المحاولات. يمكنك فقط استخدام أمر /contact للتواصل مع المطور")
                log_activity(user_id, "Blocked - CAPTCHA failed")
            else:
                num1, num2, answer = generate_captcha()
                captcha_data[user_id] = {
                    'answer': answer,
                    'attempts': captcha_info['attempts'],
                    'last_attempt': time.time()
                }
                bot.send_message(message.chat.id, f"❌ إجابة خاطئة! لديك {remaining_attempts} محاولات باقية:\n{num1} + {num2} = ؟")
    except:
        bot.send_message(message.chat.id, "❌ الرجاء إدخال رقم صحيح فقط!")

def send_real_welcome(message):
    user = message.from_user
    total_users = len(user_sessions)
    
    welcome_text = f"""
{DECOR}
✨ **مرحباً {user.first_name}!** ✨
📊 **إحصائيات البوت**: 
👥 المستخدمين: {total_users}
🛠️ الطلبات اليوم: {len(last_used_time)}
💰 نقاطك: {USER_POINTS.get(user.id, 0)}
{DECOR}
➖ **أرسل فكرتك وسأصنع لك تطبيقاً خلال ثواني!** ➖
📌 القواعد: {RULES_LINK}
    """
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 جرب مثال", callback_data="example"),
               InlineKeyboardButton("📜 المطورين", url=f"https://t.me/{RULES_LINK[1:]}"))
    markup.add(InlineKeyboardButton("💎 نظام VIP", callback_data="vip_info"),
               InlineKeyboardButton("🎁 هديتك اليومية", callback_data="daily_gift"))
    markup.add(InlineKeyboardButton("📞 تواصل مع المطور", callback_data="contact_dev"))
    
    bot.send_photo(message.chat.id, photo=WELCOME_IMAGE_URL, caption=welcome_text, reply_markup=markup)
    log_activity(user.id, "Passed welcome screen")

# ========== نظام التواصل مع المطور ==========
@bot.message_handler(commands=['contact'])
def contact_developer(message):
    user_id = message.from_user.id
    if len(message.text.split()) > 1:
        # إذا كانت الرسالة تحتوي على نص
        msg = message.text.split(' ', 1)[1]
        bot.send_message(IDADMIN, f"📩 رسالة جديدة من المستخدم {user_id}:\n{msg}")
        bot.send_message(message.chat.id, "✅ تم إرسال رسالتك إلى المطور")
        log_activity(user_id, f"Sent message to admin: {msg[:50]}...")
    else:
        # إذا كان الأمر فقط /contact بدون نص
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("إغلاق", callback_data="close_contact"))
        
        sent_msg = bot.send_message(message.chat.id, """
🛎️ مرحبا بك في مركز التواصل مع المطور!
اكتب رسالتك وسأقوم بإرسالها مباشرة للمطور.

مثال:
/contact أريد مساعدة في استخدام البوت
""", reply_markup=markup)
        
        # حفظ حالة المستخدم للرد على الرسالة التالية
        user_sessions[user_id] = {'waiting_for_contact_msg': True, 'contact_msg_id': sent_msg.message_id}

@bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get('waiting_for_contact_msg'))
def handle_contact_message(message):
    user_id = message.from_user.id
    bot.send_message(IDADMIN, f"📩 رسالة جديدة من المستخدم {user_id}:\n{message.text}")
    bot.send_message(message.chat.id, "✅ تم إرسال رسالتك إلى المطور")
    log_activity(user_id, f"Sent message to admin: {message.text[:50]}...")
    
    # إزالة حالة الانتظار
    user_sessions[user_id].pop('waiting_for_contact_msg', None)
    try:
        bot.delete_message(message.chat.id, user_sessions[user_id]['contact_msg_id'])
    except:
        pass

# ========== نظام VIP ==========
@bot.callback_query_handler(func=lambda call: call.data == 'vip_info')
def vip_info_callback(call):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("شراء VIP (50 نقطة)", callback_data="buy_vip"))
    markup.add(InlineKeyboardButton("التحقق من كود VIP", callback_data="check_vip"))
    
    bot.send_message(call.message.chat.id, """
💎 مميزات العضوية VIP:
✔️ إنشاء عدد غير محدود من المشاريع
✔️ أولوية في الدعم الفني
✔️ مميزات حصرية

لشراء عضوية VIP لمدة يومين:
- تكلفة 50 نقطة
- اضغط على زر الشراء أدناه
""", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'buy_vip')
def buy_vip(call):
    user_id = call.from_user.id
    if USER_POINTS.get(user_id, 0) >= 50:
        # إنشاء كود VIP عشوائي
        vip_code = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:8].upper()
        VIP_CODES[vip_code] = {
            'user_id': user_id,
            'expiry': time.time() + 172800  # يومين
        }
        
        USER_POINTS[user_id] -= 50
        bot.send_message(user_id, f"""
🎉 تم شراء عضوية VIP بنجاح!
🔑 كود VIP الخاص بك: {vip_code}
📅 تنتهي العضوية بعد يومين

استخدم الأمر /vip ثم اختر "التحقق من كود VIP" لتفعيل العضوية
""")
    else:
        bot.answer_callback_query(call.id, "❌ لا تمتلك نقاط كافية (تحتاج 50 نقطة)")

@bot.callback_query_handler(func=lambda call: call.data == 'check_vip')
def ask_vip_code(call):
    user_id = call.from_user.id
    sent_msg = bot.send_message(user_id, "🔑 الرجاء إرسال كود VIP الخاص بك:")
    user_sessions[user_id] = {'waiting_for_vip_code': True, 'vip_msg_id': sent_msg.message_id}

@bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get('waiting_for_vip_code'))
def activate_vip(message):
    user_id = message.from_user.id
    vip_code = message.text.upper()
    
    if vip_code in VIP_CODES and VIP_CODES[vip_code]['user_id'] == user_id:
        expiry_date = datetime.fromtimestamp(VIP_CODES[vip_code]['expiry']).strftime('%Y-%m-%d %H:%M')
        VIP_USERS[user_id] = VIP_CODES[vip_code]['expiry']
        del VIP_CODES[vip_code]
        
        bot.send_message(user_id, f"""
🎊 تم تفعيل عضوية VIP بنجاح!
⏳ تنتهي العضوية في: {expiry_date}
""")
    else:
        bot.send_message(user_id, "❌ كود VIP غير صحيح أو منتهي الصلاحية")
    
    # إزالة حالة الانتظار
    user_sessions[user_id].pop('waiting_for_vip_code', None)
    try:
        bot.delete_message(message.chat.id, user_sessions[user_id]['vip_msg_id'])
    except:
        pass

# ========== نظام الهدايا اليومية ==========
@bot.callback_query_handler(func=lambda call: call.data == 'daily_gift')
def daily_gift_callback(call):
    user_id = call.from_user.id
    today = datetime.now().strftime('%Y-%m-%d')
    
    if DAILY_GIFT_COOLDOWN.get(user_id) != today:
        points_to_add = 15
        USER_POINTS[user_id] = USER_POINTS.get(user_id, 0) + points_to_add
        DAILY_GIFT_COOLDOWN[user_id] = today
        
        bot.send_message(user_id, f"""
🎁 هديتك اليومية:
+{points_to_add} نقطة!
💰 رصيدك الحالي: {USER_POINTS[user_id]} نقطة
""")
    else:
        bot.answer_callback_query(call.id, "⏳ لقد استلمت هديتك اليومية بالفعل، عد غداً!")

# ========== نظام توليد التطبيقات ==========
def handle_generation(message, query_text=None):
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        if user_id in blocked_users:
            bot.send_message(message.chat.id, "❌ أنت محظور! يمكنك فقط استخدام أمر /contact للتواصل مع المطور")
            return
        elif user_id in last_used_time:
            wait_time = round(FLOOD_SECONDS - (time.time() - last_used_time[user_id]))
            bot.send_message(message.chat.id, f"⏳ يرجى الانتظار {wait_time} ثانية قبل الطلب التالي")
            return
    
    # التحقق من عدد المشاريع للمستخدم العادي
    if user_id not in VIP_USERS and user_analytics.get(user_id, {}).get("generated_apps", 0) >= MAX_PROJECTS_PER_USER:
        bot.send_message(message.chat.id, f"""
❌ لقد وصلت إلى الحد الأقصى للمشاريع ({MAX_PROJECTS_PER_USER})!
💎 يمكنك ترقية حسابك إلى VIP لإنشاء المزيد من المشاريع
""")
        return
    
    last_used_time[user_id] = time.time()
    query = query_text or message.text
    chat_logs[user_id] = chat_logs.get(user_id, []) + [query]
    
    bot.send_chat_action(message.chat.id, 'upload_document')
    bot.send_message(message.chat.id, get_personality_response())
    loading_msg = bot.send_message(message.chat.id, "⌛ جاري إنشاء التطبيق...")
    log_activity(user_id, f"Requested: {query[:50]}...")

    try:
        headers = {
            'authority': 'appgen.groqlabs.com',
            'accept': '*/*',
            'content-type': 'application/json',
            'origin': 'https://appgen.groqlabs.com',
            'referer': 'https://appgen.groqlabs.com/',
            'user-agent': 'Mozilla/5.0'
        }

        json_data = {
            'query': query,
            'currentHtml': '',
            'drawingData': None,
            'theme': 'light',
            'model': 'meta-llama/llama-4-maverick-17b-128e-instruct',
            'stream': True,
            'sessionId': UUID,
            'version': '1',
        }

        response = requests.post('https://appgen.groqlabs.com/api/generate', 
                               headers=headers, 
                               json=json_data, 
                               timeout=30)
        response.raise_for_status()
        
        full_html = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if data.get("type") == "chunk":
                    full_html += data.get("content", "")
                elif data.get("type") == "complete":
                    full_html += data.get("html", "")

        file = io.BytesIO(full_html.encode('utf-8'))
        file.name = "تطبيق_مولد.txt"
        bot.send_document(message.chat.id, file)
        user_sessions[user_id] = full_html

        bot.send_message(message.chat.id, f"""
✅ **تم الإنشاء بنجاح!**
🌐 جرب تطبيقك الآن: https://preview.example.com/{hashlib.md5(full_html.encode()).hexdigest()}
""")
        
        # تحديث الإحصائيات
        if user_id not in user_analytics:
            user_analytics[user_id] = {"generated_apps": 0, "rank": "مبتدئ"}
        user_analytics[user_id]["generated_apps"] += 1
        
        # منح النقاط حسب الرتبة
        current_rank = user_analytics[user_id].get("rank", "مبتدئ")
        points_to_add = RANK_POINTS.get(current_rank, 0)
        USER_POINTS[user_id] = USER_POINTS.get(user_id, 0) + points_to_add
        
        bot.send_message(message.chat.id, f"""
🎉 تم منحك {points_to_add} نقطة!
💰 رصيدك الحالي: {USER_POINTS[user_id]} نقطة
""")
        
        update_rank(user_id)
        send_rating(message)
        bot.send_message(message.chat.id, random.choice(encouragement))
        
        # عرض اقتراحات الذكاء الاصطناعي
        if "متجر" in query:
            ai_suggestions(user_id, "متجر")
        elif "موقع" in query:
            ai_suggestions(user_id, "موقع")
        elif "أداة" in query:
            ai_suggestions(user_id, "أداة")
            
        log_activity(user_id, "Received generated app")

    except requests.exceptions.RequestException as e:
        bot.edit_message_text("🔌 حدث مشكلة في الاتصال بالخادم، يرجى المحاولة لاحقاً", 
                            message.chat.id, 
                            loading_msg.message_id)
        send_admin_notification(f"⚠️ فشل اتصال API:\n{e}")
        log_activity(user_id, f"API Error: {e}")
    except Exception as e:
        bot.edit_message_text("⚠️ حدث خطأ غير متوقع، الرجاء إعادة المحاولة", 
                            message.chat.id, 
                            loading_msg.message_id)
        send_admin_notification(f"🛑 خطأ غير متوقع:\n{e}")
        logging.error(f"Error: {e}")
        log_activity(user_id, f"Unexpected Error: {e}")

# ========== نظام التقييم ==========
def send_rating(message):
    markup = InlineKeyboardMarkup()
    buttons = [
        InlineKeyboardButton("⭐ 1", callback_data="rate_1"),
        InlineKeyboardButton("⭐⭐ 2", callback_data="rate_2"),
        InlineKeyboardButton("⭐⭐⭐ 3", callback_data="rate_3"),
        InlineKeyboardButton("⭐⭐⭐⭐ 4", callback_data="rate_4"),
        InlineKeyboardButton("⭐⭐⭐⭐⭐ 5", callback_data="rate_5"),
        InlineKeyboardButton("✖️ إلغاء", callback_data="rate_cancel")
    ]
    markup.add(*buttons[:3])
    markup.add(*buttons[3:5])
    markup.add(buttons[5])
    bot.send_message(message.chat.id, "✨ كيف تقيم تجربتك مع البوت؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_'))
def handle_rating(call):
    user_id = call.from_user.id
    if call.data == "rate_cancel":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
    
    if user_id in user_ratings:
        bot.answer_callback_query(call.id, "❗ قيمت سابقاً، شكراً لك")
        return
    
    rating = int(call.data.split('_')[1])
    user_ratings[user_id] = rating
    
    responses = {
        1: "😞 شكراً لرأيك! سنعمل على التحسين",
        2: "🙂 نقدر ملاحظاتك وسنطور البوت أكثر",
        3: "😃 شكراً لك! سنستمر بالتطوير",
        4: "👍 رأيك مهم لنا! شكراً لدعمك",
        5: "🚀 رائع! شكراً لتقييمك الممتاز"
    }
    
    bot.answer_callback_query(call.id, f"تم تسجيل تقييمك: {rating} نجوم")
    bot.send_message(call.message.chat.id, responses.get(rating, "شكراً لك!"))
    log_activity(user_id, f"Rated {rating} stars")

# ========== نظام الإدارة ==========
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in admins:
        bot.send_message(message.chat.id, "❌ ليس لديك صلاحية الوصول!")
        return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("إعطاء نقاط", callback_data="admin_give_points"))
    markup.add(InlineKeyboardButton("إنشاء هدية", callback_data="admin_create_gift"))
    
    admin_menu = f"""
⚙️ **لوحة التحكم الإدارية** ⚙️
👤 الأدمن: {len(admins)}
🔴 المحظورين: {len(blocked_users)}
💰 إجمالي النقاط الموزعة: {sum(USER_POINTS.values())}

📊 الأوامر المتاحة:
/give_points [النقاط] [ايدي] - إعطاء نقاط
/create_gift [النقاط] - إنشاء هدية للجميع
"""
    bot.send_message(message.chat.id, admin_menu, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'admin_give_points')
def admin_give_points(call):
    user_id = call.from_user.id
    sent_msg = bot.send_message(user_id, "💎 أرسل عدد النقاط ثم ايدي المستخدم (مثال: 50 123456789):")
    user_sessions[user_id] = {'waiting_for_give_points': True, 'give_points_msg_id': sent_msg.message_id}

@bot.message_handler(func=lambda m: user_sessions.get(m.from_user.id, {}).get('waiting_for_give_points'))
def handle_give_points(message):
    user_id = message.from_user.id
    try:
        points, target_id = message.text.split()
        points = int(points)
        target_id = int(target_id)
        
        USER_POINTS[target_id] = USER_POINTS.get(target_id, 0) + points
        bot.send_message(message.chat.id, f"✅ تم إعطاء {points} نقطة للمستخدم {target_id}")
        bot.send_message(target_id, f"🎁 لقد تلقيت {points} نقطة من الأدمن!")
    except:
        bot.send_message(message.chat.id, "❌ استخدام خاطئ! أرسل عدد النقاط ثم ايدي المستخدم (مثال: 50 123456789)")
    
    # إزالة حالة الانتظار
    user_sessions[user_id].pop('waiting_for_give_points', None)
    try:
        bot.delete_message(message.chat.id, user_sessions[user_id]['give_points_msg_id'])
    except:
        pass

@bot.message_handler(commands=['give_points'])
def give_points_command(message):
    if message.from_user.id not in admins:
        return
    
    try:
        _, points, target_id = message.text.split()
        points = int(points)
        target_id = int(target_id)
        
        USER_POINTS[target_id] = USER_POINTS.get(target_id, 0) + points
        bot.send_message(message.chat.id, f"✅ تم إعطاء {points} نقطة للمستخدم {target_id}")
        bot.send_message(target_id, f"🎁 لقد تلقيت {points} نقطة من المطور!")
    except:
        bot.send_message(message.chat.id, "❌ استخدام خاطئ! /give_points [النقاط] [ايدي المستخدم]")

# ========== معالجة الرسائل العامة ==========
@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    
    # التحقق من المستخدمين الجدد
    if user_id not in last_used_time:
        if user_id not in new_user_warnings:
            new_user_warnings[user_id] = 1
            bot.send_message(message.chat.id, f"⚠️ تنبيه: يرجى قراءة القواعد {RULES_LINK} قبل الاستخدام")
        elif new_user_warnings[user_id] < 3:
            new_user_warnings[user_id] += 1
            bot.send_message(message.chat.id, f"❗ لم تقرأ القواعد بعد! {RULES_LINK}")
        else:
            blocked_users.add(user_id)
            bot.send_message(message.chat.id, "❌ تم حظرك بسبب عدم الالتزام بالقواعد")
            send_admin_notification(f"🔴 تم حظر مستخدم جديد: {user_id}")
            return
    
    # التحقق من المحتوى الضار
    if contains_blacklist_words(message.text) or is_potential_attack(message.text):
        blocked_users.add(user_id)
        bot.send_message(message.chat.id, "⛔ تم حظرك بسبب محتوى غير مسموح")
        send_admin_notification(f"🚨 تم حظر مستخدم بسبب محتوى ضار: {user_id}")
        return
    
    # معالجة الطلب
    if message.content_type == 'text':
        handle_generation(message)
    else:
        bot.reply_to(message, "❌ **لا أستطيع معالجة الملفات أو الصور حالياً**\nأرسل نصاً فقط مثل: \"اصنع لي تطبيقاً بسيطاً\"")

# ========== تشغيل البوت ==========
if __name__ == '__main__':
    load_backup()  # تحميل النسخة الاحتياطية
    logging.info("Starting bot...")
    send_admin_notification("🤖 البوت يعمل الآن!")
    
    # بدء خيط النسخ الاحتياطي التلقائي
    def backup_job():
        while True:
            time.sleep(3600)  # كل ساعة
            save_backup()
            logging.info("تم عمل نسخة احتياطية تلقائية")
    
    backup_thread = threading.Thread(target=backup_job, daemon=True)
    backup_thread.start()
    
    # بدء خيط التحديثات التلقائية
    update_thread = threading.Thread(target=lambda: [
        time.sleep(3600),
        send_admin_notification("🔄 البوت يعمل بشكل طبيعي")
    ], daemon=True)
    update_thread.start()
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except Exception as e:
            logging.error(f"Bot crashed: {e}")
            send_admin_notification(f"💥 البوت تحطم:\n{e}")
            time.sleep(15)
            logging.info("Restarting bot...")

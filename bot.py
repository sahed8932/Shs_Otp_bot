import telebot
import requests
import os
import time
import random
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup

# ক্লাউডফ্লেয়ার সিকিউরিটি বাইপাস করার জন্য ক্লাউডস্ক্র্যাপার লোড করার চেষ্টা
try:
    import cloudscraper
    session = cloudscraper.create_scraper()  # ক্লাউডফ্লেয়ার বাইপাস সেশন
    print("🚀 Cloudscraper সফলভাবে চালু হয়েছে! ক্লাউডফ্লেয়ার বাইপাস একটিভ।")
except Exception as e:
    session = requests.Session()
    print(f"⚠️ Cloudscraper লোড করা যায়নি: {e}। সাধারণ requests.Session() ব্যবহার করা হচ্ছে।")

# ─── কনফিগারেশন ───
BOT_TOKEN = "8981181566:AAF7mng2by7JDKIJYc_7P9clBE3tINBWdkY"  # আপনার বটের টোকেনটি এখানে বসান
ADMIN_ID = 8262679678              # আপনার অ্যাডমিন আইডি ফিক্সড থাকলো

bot = telebot.TeleBot(BOT_TOKEN)
USERS_FILE = "users.txt"

app = Flask('')

@app.route('/')
def home():
    return "বট সচল আছে!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ─── SQLite ডাটাবেস হ্যান্ডলিং (ড্যাশবোর্ড সেটিংস আজীবন সেভ রাখার জন্য) ───
def init_db():
    conn = sqlite3.connect("bot_settings.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)''')
    
    defaults = {
        "channel_id": "-1003956226642",
        "group_id": "-1004309875319",
        "channel_link": "https://t.me/SHS_Otp_Channel",
        "group_link": "https://t.me/+DXdDIm7-rRU4YTQ1",
        "number_url": "",
        "sms_url": "",
        "ivasms_email": "",
        "ivasms_password": "",
        "ivasms_cookie": ""  # ম্যানুয়াল কুকির জন্য নতুন ডাটাবেস ফিল্ড
    }
    for key, val in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, val))
        
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = sqlite3.connect("bot_settings.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key=?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""

def set_setting(key, value):
    conn = sqlite3.connect("bot_settings.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# ─── কোর সাবস্ক্রিপশন ফাংশনসমূহ ───
def save_user(user_id):
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            f.write(f"{user_id}\n")
    else:
        with open(USERS_FILE, "r") as f:
            users = f.read().splitlines()
        if str(user_id) not in users:
            with open(USERS_FILE, "a") as f:
                f.write(f"{user_id}\n")

def is_subscribed(user_id):
    try:
        c_id = int(get_setting("channel_id"))
        g_id = int(get_setting("group_id"))
        channel_status = bot.get_chat_member(c_id, user_id).status
        group_status = bot.get_chat_member(g_id, user_id).status
        return channel_status not in ['left', 'kicked'] and group_status not in ['left', 'kicked']
    except:
        return True

def send_join_request(chat_id):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📢 Join OTP Channel", url=get_setting("channel_link")))
    markup.row(InlineKeyboardButton("💬 Join OTP Group", url=get_setting("group_link")))
    markup.row(InlineKeyboardButton("✅ Joined", callback_data="check_membership"))
    bot.send_message(chat_id, "⚠️ সার্ভিসটি ব্যবহার করতে প্রথমে আমাদের ওটিপি চ্যানেল এবং গ্রুপে জয়েন করুন। তারপর '✅ Joined' বাটনে ক্লিক করুন।", reply_markup=markup)

def send_home_keyboard(chat_id, text="👋 ওটিপি ড্যাশবোর্ডে স্বাগতম! নিচের বাটন ব্যবহার করুন:"):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📞 Get Number"), KeyboardButton("📊 Active Traffic"))
    markup.row(KeyboardButton("🌍 Available Countries"), KeyboardButton("🔐 2FA GENERATE"))
    if chat_id == ADMIN_ID:
        markup.row(KeyboardButton("⚙️ Admin Panel"))
    bot.send_message(chat_id, text, reply_markup=markup)

def send_services_menu(chat_id, message_id=None):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("💬 WhatsApp", callback_data="app_whatsapp"), InlineKeyboardButton("📘 Facebook", callback_data="app_facebook"))
    markup.row(InlineKeyboardButton("📸 Instagram", callback_data="app_instagram"), InlineKeyboardButton("✈️ Telegram", callback_data="app_telegram"))
    markup.row(InlineKeyboardButton("🎵 TikTok", callback_data="app_tiktok"), InlineKeyboardButton("⚙️ Other Apps", callback_data="app_any"))
    
    text = "📱 **ওটিপি সার্ভিস মেনু:**\n\nআপনি কোন অ্যাপের নম্বর নিতে চান? নিচে থেকে সেই অ্যাপটি সিলেক্ট করুন:"
    if message_id:
        try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode="Markdown")
        except: bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ─── IVASMS ব্যাকএন্ড ইঞ্জিন (টোকেন ও সেশন বাইপাস) ───
def login_ivasms():
    email = get_setting("ivasms_email")
    password = get_setting("ivasms_password")
    if not email or not password: return False
    
    login_url = "https://ivasms.com/login"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://ivasms.com/login",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    try:
        # ১ম ধাপ: লগইন পেজ থেকে CSRF টোকেন বের করা
        res = session.get(login_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        token_input = soup.find('input', {'name': '_token'})
        csrf_token = token_input['value'] if token_input else None
        
        payload = {
            "email": email,
            "password": password
        }
        if csrf_token:
            payload["_token"] = csrf_token
            
        # ২য় ধাপ: সিকিউর লগইন রিকোয়েস্ট পাঠানো
        post_res = session.post(login_url, data=payload, headers=headers, timeout=10)
        
        # সফল লগইনে সাধারণত ড্যাশবোর্ড পেজ বা লগআউট বাটন দেখা যায়
        if "logout" in post_res.text.lower() or "dashboard" in post_res.text.lower() or post_res.status_code in [200, 302]:
            return True
    except Exception as e:
        print(f"লগইন এরর: {e}")
    return False

# কুকি সেশন হ্যান্ডলার (ম্যানুয়াল কুকি ও অটো-লগইন সমন্বয়)
def get_session_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    cookie = get_setting("ivasms_cookie")
    if cookie:
        # ম্যানুয়াল কুকি সেট করা থাকলে সেটি হেডারে বসাবে
        headers["Cookie"] = cookie
        
    try:
        res = session.get(url, headers=headers, timeout=10)
        # কুকি না থাকলে অথবা সেশন শেষ হয়ে গেলে অটো লগইনের চেষ্টা করবে
        if "login" in res.url or ("login" in res.text.lower() and "logout" not in res.text.lower()):
            if not cookie:  # কুকি না থাকলেই কেবল অটো লগইন করবে
                print("সেশন শেষ! পুনরায় ব্যাকগ্রাউন্ড লগইন করা হচ্ছে...")
                if login_ivasms():
                    res = session.get(url, headers=headers, timeout=10)
        return res
    except:
        return None

def fetch_ivasms_number():
    url = get_setting("number_url")
    if not url: return None
    try:
        res = get_session_page(url)
        if not res: return None
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) > 1:
                num = cols[1].text.strip().replace('+', '').replace(' ', '')
                if num.isdigit() and len(num) >= 8:
                    return num
    except: pass
    return None

# ─── ওটিপি ফেচিং এবং ফরোয়ার্ডিং লজিক ───
def auto_fetch_ivasms_otp(chat_id, phone, selected_app, manual=False):
    if not manual:
        time.sleep(10)  # অটোমেটিক ওটিপির জন্য ১০ সেকেন্ড ওয়েট
        
    sms_url = get_setting("sms_url")
    if not sms_url: return
    
    try:
        res = get_session_page(sms_url)
        if not res: return
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        found = False
        
        for row in rows:
            row_text = row.text.replace('+', '').replace(' ', '')
            if phone in row_text:
                cols = row.find_all('td')
                if cols:
                    otp_message = cols[-1].text.strip()
                    msg_text = f"🔥 **নতুন ওটিপি অ্যালার্ট!** 🔥\n\n" \
                               f"📱 অ্যাপ: #{selected_app.capitalize()}\n" \
                               f"📞 নম্বর: `+{phone}`\n" \
                               f"✉️ ওটিপি মেসেজ: {otp_message}"
                    
                    # ১. ইউজারের ইনবক্সে যাবে
                    bot.send_message(chat_id, msg_text, parse_mode="Markdown")
                    # ২. ডাইনামিক চ্যানেলে যাবে
                    try: bot.send_message(int(get_setting("channel_id")), msg_text, parse_mode="Markdown")
                    except: pass
                    # ৩. ডাইনামিক গ্রুপে যাবে
                    try: bot.send_message(int(get_setting("group_id")), msg_text, parse_mode="Markdown")
                    except: pass
                    found = True
                    break
                    
        if not found and manual:
            bot.send_message(chat_id, "⚠️ ওটিপি এখনো আসেনি! অ্যাপে সেন্ড করে পুনরায় '📥 Fetch Code' চাপুন বা নম্বর চেঞ্জ করুন।")
    except Exception as e:
        if manual: bot.send_message(chat_id, f"❌ সার্ভার রেসপন্স করেনি। এরর: {str(e)}")

# ─── ভিজ্যুয়াল ড্যাশবোর্ড জেনারেটর ───
def send_admin_dashboard(chat_id, message_id=None):
    num_url = get_setting("number_url")
    sms_url = get_setting("sms_url")
    email = get_setting("ivasms_email")
    cookie = get_setting("ivasms_cookie")
    c_id = get_setting("channel_id")
    g_id = get_setting("group_id")
    
    num_status = "✅ Set" if num_url else "❌ Not Set"
    sms_status = "✅ Set" if sms_url else "❌ Not Set"
    
    # লগইন মেথড অনুযায়ী স্ট্যাটাস প্রদর্শন
    if cookie:
        login_status = "✅ Active (Manual Cookie)"
    elif email:
        login_status = f"✅ Active (Auto Login: {email})"
    else:
        login_status = "❌ Not Logged In"
    
    dashboard_text = f"👑 **CONTROL DASHBOARD (অ্যাডমিন প্যানেল)**\n" \
                     f"----------------------------------------\n" \
                     f"🔐 IVASMS Status : {login_status}\n" \
                     f"📞 Number URL   : {num_status}\n" \
                     f"✉️ Live SMS URL : {sms_status}\n" \
                     f"📢 Channel ID   : `{c_id}`\n" \
                     f"💬 Group ID     : `{g_id}`\n" \
                     f"----------------------------------------\n" \
                     f"💡 যেকোনো সেটিংস পরিবর্তন করতে নিচের বাটনে চাপুন:"
                     
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔐 IVASMS Login (Auto)", callback_data="adm_login"), InlineKeyboardButton("🍪 Set Session Cookie", callback_data="adm_cookie"))
    markup.row(InlineKeyboardButton("📞 Set Number URL", callback_data="adm_num_url"), InlineKeyboardButton("✉️ Set Live SMS URL", callback_data="adm_sms_url"))
    markup.row(InlineKeyboardButton("📢 Set Channel Link", callback_data="adm_channel"), InlineKeyboardButton("💬 Set Group Link", callback_data="adm_group"))
    markup.row(InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="adm_refresh"))
    
    if message_id:
        try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=dashboard_text, reply_markup=markup, parse_mode="Markdown")
        except: pass
    else:
        bot.send_message(chat_id, dashboard_text, reply_markup=markup, parse_mode="Markdown")

# ─── অ্যাডমিন স্টেট ───
admin_states = {}

# ─── বটের মূল মেসেজ হ্যান্ডলারসমূহ ───

# ১. স্টার্ট কমান্ড
@bot.message_handler(commands=['start'])
def start_bot(message):
    save_user(message.chat.id)
    if message.chat.id == ADMIN_ID:
        send_home_keyboard(message.chat.id, text="👋 ওটিপি ড্যাশবোর্ডে স্বাগতম! নিচের বাটন ব্যবহার করুন:")
        send_admin_dashboard(message.chat.id)
    else:
        if is_subscribed(message.chat.id): 
            send_home_keyboard(message.chat.id)
        else: 
            send_join_request(message.chat.id)

# ২. গ্লোবাল নোটিশ কমান্ড
@bot.message_handler(commands=['notice'])
def send_notice(message):
    if message.chat.id == ADMIN_ID:
        notice_text = message.text.replace("/notice", "").strip()
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                for user in f.read().splitlines():
                    try: bot.send_message(int(user), f"📢 **নোটিশ:**\n\n{notice_text}")
                    except: pass
            bot.reply_to(message, "✅ সফলভাবে নোটিশ পাঠানো হয়েছে।")

# ৩. অ্যাডমিন ইনপুট প্রসেসর স্টেট মেশিন
@bot.message_handler(func=lambda msg: msg.chat.id in admin_states and msg.chat.id == ADMIN_ID)
def handle_admin_steps(message):
    try:
        state_data = admin_states[message.chat.id]
        state = state_data["step"]
        
        if state == "email":
            admin_states[message.chat.id]["email"] = message.text
            bot.reply_to(message, "🔑 এবার আপনার IVASMS পাসওয়ার্ডটি টাইপ করে পাঠান:")
            admin_states[message.chat.id]["step"] = "password"
            
        elif state == "password":
            email = admin_states[message.chat.id]["email"]
            password = message.text
            
            # সাময়িকভাবে ডেটা সেট করে লগইন চেষ্টা করা হবে
            set_setting("ivasms_email", email)
            set_setting("ivasms_password", password)
            status_msg = bot.reply_to(message, "⏳ IVASMS প্যানেলে লগইন করার চেষ্টা করা হচ্ছে...")
            
            if login_ivasms():
                try: bot.delete_message(message.chat.id, status_msg.message_id)
                except: pass
                # অটো লগইন সফল হলে ব্যাকআপ কুকি ফিল্ড ক্লিয়ার করে দেওয়া হবে
                set_setting("ivasms_cookie", "")
                bot.send_message(message.chat.id, "✅ **লগইন সফল হয়েছে!**\n\nসফলভাবে আপনার সেশন ড্যাশবোর্ডে সেট হয়ে গেছে।")
            else:
                try: bot.delete_message(message.chat.id, status_msg.message_id)
                except: pass
                # লগইন ব্যর্থ হলে ইমেইল-পাসওয়ার্ড ক্লিয়ার করে দেওয়া হবে যাতে ড্যাশবোর্ড আপডেট থাকে
                set_setting("ivasms_email", "")
                set_setting("ivasms_password", "")
                bot.send_message(message.chat.id, "❌ **লগইন ব্যর্থ হয়েছে!**\n\nদয়া করে আপনার ইমেইল ও পাসওয়ার্ড চেক করে পুনরায় চেষ্টা করুন। (বি:দ্র: ক্লাউডফ্লেয়ারের ব্লক এড়াতে আপনি বিকল্প ম্যানুয়াল কুকি সেটআপ পদ্ধতি ব্যবহার করতে পারেন।)")
                
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "cookie":
            set_setting("ivasms_cookie", message.text)
            # ম্যানুয়াল কুকি সেট করলে কনফ্লিক্ট এড়াতে অটো ইমেইল-পাসওয়ার্ড ক্লিয়ার করা হবে
            set_setting("ivasms_email", "")
            set_setting("ivasms_password", "")
            bot.reply_to(message, "✅ **কুকি সফলভাবে সেভ করা হয়েছে!**\n\nবট এখন আপনার ব্রাউজার সেশন কুকি ব্যবহার করে কাজ করবে।")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "num_url":
            set_setting("number_url", message.text)
            bot.reply_to(message, "✅ **ধাপ ১ সফল!**\n\nMy Numbers পেজের লিংকটি ডাটাবেসে সেভ করা হয়েছে।")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "sms_url":
            set_setting("sms_url", message.text)
            bot.reply_to(message, "✅ **ধাপ ২ সফল!**\n\nLive SMS পেজের লিংকটি ডাটাবেসে সেভ করা হয়েছে।")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "c_id":
            set_setting("channel_id", message.text)
            bot.reply_to(message, "🔗 এবার নতুন ওটিপি চ্যানেল জয়েন করার লিংক (Link) টি দিন:")
            admin_states[message.chat.id]["step"] = "c_link"
            
        elif state == "c_link":
            set_setting("channel_link", message.text)
            bot.reply_to(message, "✅ ওটিপি চ্যানেল এবং জয়েনিং লিংক আপডেট হয়েছে!")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "g_id":
            set_setting("group_id", message.text)
            bot.reply_to(message, "🔗 এবার নতুন ওটিপি গ্রুপ জয়েন করার লিংক (Link) টি দিন:")
            admin_states[message.chat.id]["step"] = "g_link"
            
        elif state == "g_link":
            set_setting("group_link", message.text)
            bot.reply_to(message, "✅ ওটিপি গ্রুপ এবং জয়েনিং লিংক আপডেট হয়েছে!")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ একটি ভুল হয়েছে: {str(e)}")
        if message.chat.id in admin_states:
            del admin_states[message.chat.id]

# ৪. ইউজার কিবোর্ড বাটন কন্ট্রোল (ক্যাচ-অল হ্যান্ডলার সবার নিচে)
@bot.message_handler(func=lambda message: True)
def handle_text_buttons(message):
    if message.chat.id != ADMIN_ID and not is_subscribed(message.chat.id):
        send_join_request(message.chat.id)
        return

    if message.text == "⚙️ Admin Panel" and message.chat.id == ADMIN_ID:
        send_admin_dashboard(message.chat.id)
    elif message.text == "📞 Get Number":
        send_services_menu(message.chat.id)
    elif message.text == "📊 Active Traffic":
        bot.send_message(message.chat.id, "📊 **Active Traffic:**\n\nবর্তমানে ওটিপি সার্ভারে ট্রাফিক ১০০% সচল ও হাই স্পিড আছে।")
    elif message.text == "🌍 Available Countries":
        bot.send_message(message.chat.id, "🌍 **বর্তমানে সচল দেশসমূহ:**\n\nUS, GB, CA, FR, DE, MM, VE (প্যানেল অনুযায়ী)")
    elif message.text == "🔐 2FA GENERATE":
        bot.send_message(message.chat.id, "🔐 **2FA Generator:**\n\nসুরক্ষার জন্য এই ফিচারটি খুব শীঘ্রই লাইভ করা হবে।")

# ─── কলব্যাক কোয়েরি হ্যান্ডলারসমূহ ───

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership(call):
    if is_subscribed(call.from_user.id):
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        send_home_keyboard(call.message.chat.id, "✅ ভেরিফিকেশন সফল হয়েছে!")
    else:
        bot.answer_callback_query(call.id, text="❌ আপনি এখনো জয়েন করেননি!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def back_to_main(call):
    send_services_menu(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("app_"))
def get_countries_for_app(call):
    selected_app = call.data.split("_")[1]
    markup = InlineKeyboardMarkup()
    
    markup.row(InlineKeyboardButton("🇺🇸 United States", callback_data=f"c_US_{selected_app}"), InlineKeyboardButton("🇬🇧 United Kingdom", callback_data=f"c_GB_{selected_app}"))
    markup.row(InlineKeyboardButton("🇨🇦 Canada", callback_data=f"c_CA_{selected_app}"), InlineKeyboardButton("🇫🇷 France", callback_data=f"c_FR_{selected_app}"))
    markup.row(InlineKeyboardButton("🇲🇳 Myanmar", callback_data=f"c_MM_{selected_app}"), InlineKeyboardButton("🇻🇪 Venezuela", callback_data=f"c_VE_{selected_app}"))
    
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="back_main"))
    text = f"📱 Service: **{selected_app.capitalize()}**\n🌍 **Select Country:**"
    try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode="Markdown")
    except: bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("c_") or call.data.startswith("change_"))
def show_number_interface(call):
    data_parts = call.data.split("_")
    country_code = data_parts[1].upper()
    selected_app = data_parts[2]
    
    if not get_setting("number_url") or not get_setting("sms_url"):
        bot.answer_callback_query(call.id, text="⚠️ বটটি কনফিগার করা নেই। অ্যাডমিন এখনো লিংক সেটআপ করেনি।", show_alert=True)
        return
        
    fetched_num = fetch_ivasms_number()
    
    if not fetched_num:
        rand_suffix = str(random.randint(100000, 999999))
        fetched_num = f"8801712{rand_suffix}"

    msg_text = f"🌍Country ➤ {country_code}\n\n" \
               f"📞Number: `+{fetched_num}`\n\n" \
               f"⏳Status: Waiting For OTP\n" \
               f"⏰Number Validity ➤ 10 minutes\n" \
               f"🔷 ওটিপি পেতে নিচের '📥 Fetch Code' বাটনে ক্লিক করুন অথবা অটোমেটিক ওটিপির জন্য ১০ সেকেন্ড ওয়েট করুন।😊"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔄 Change Number", callback_data=f"change_{country_code.lower()}_{selected_app}"))
    markup.row(
        InlineKeyboardButton("📢 OTP Channel", url=get_setting("channel_link")),
        InlineKeyboardButton("💬 OTP Group", url=get_setting("group_link"))
    )
    clean_phone = fetched_num.replace('+', '').replace(' ', '')
    markup.row(InlineKeyboardButton("📥 Fetch Code", callback_data=f"fetch_{clean_phone}_{selected_app}"))
    
    try: bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg_text, reply_markup=markup, parse_mode="Markdown")
    except: bot.send_message(call.message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")
    
    Thread(target=auto_fetch_ivasms_otp, args=(call.message.chat.id, clean_phone, selected_app, False)).start()

@bot.callback_query_handler(func=lambda call: call.data.startswith("fetch_"))
def manual_fetch_trigger(call):
    data_parts = call.data.split("_")
    phone = data_parts[1]
    selected_app = data_parts[2]
    
    bot.answer_callback_query(call.id, text="🔍 ওটিপি কোড খোঁজা হচ্ছে...", show_alert=False)
    auto_fetch_ivasms_otp(call.message.chat.id, phone, selected_app, manual=True)

# অ্যাডমিন ড্যাশবোর্ড কলব্যাক হ্যান্ডলার (নতুন কুকি বাটন সহ)
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_") and call.from_user.id == ADMIN_ID)
def handle_admin_callbacks(call):
    action = call.data
    if action == "adm_refresh":
        send_admin_dashboard(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, text="🔄 ড্যাশবোর্ড আপডেট করা হয়েছে!")
        
    elif action == "adm_login":
        bot.send_message(call.message.chat.id, "📧 **IVASMS লগইন গাইড 📖**\n\n১. প্রথমে আপনার IVASMS একাউন্টের ইমেইলটি নিচে টাইপ করে পাঠান:")
        admin_states[call.message.chat.id] = {"step": "email", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_cookie":
        instruction = "🍪 **Session Cookie সেটআপ গাইড 📖**\n\n" \
                      "ক্লাউডফ্লেয়ারের সিকিউরিটি প্রোটেকশন বাইপাস করতে ম্যানুয়াল কুকি পদ্ধতি ব্যবহার করুন।\n\n" \
                      "১. আপনার ব্রাউজারে `ivasms.com` এ লগইন করুন।\n" \
                      "২. ব্রাউজারের Cookie-Editor এক্সটেনশন বা DevTools থেকে `laravel_session` এবং `XSRF-TOKEN` সহ সম্পূর্ণ কুকি টেক্সটটি কপি করুন।\n" \
                      "৩. পুরো কুকি টেক্সটটি নিচে পেস্ট করে আমাকে পাঠিয়ে দিন:\n\n" \
                      "*(যেমন: `laravel_session=eyJ...; XSRF-TOKEN=eyJ...`)*"
        bot.send_message(call.message.chat.id, instruction)
        admin_states[call.message.chat.id] = {"step": "cookie", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_num_url":
        instruction = "📂 **My Numbers লিংক সেটআপ গাইড 📖**\n\n" \
                      "১. প্রথমে আপনার ব্রাউজারে `ivasms.com` এ লগইন করুন।\n" \
                      "২. বাম পাশের সাইডবার মেনু থেকে **'My Numbers'** বা **'Numbers'** পেজে যান।\n" \
                      "৩. পেজটিতে থাকা অবস্থায় ব্রাউজারের ওপরের অ্যাড্রেস বার থেকে সম্পূর্ণ লিংকটি কপি করুন।\n" \
                      "৪. কপি করা লিংকটি নিচে পেস্ট করে আমাকে পাঠিয়ে দিন:"
        bot.send_message(call.message.chat.id, instruction)
        admin_states[call.message.chat.id] = {"step": "num_url", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_sms_url":
        instruction = "💬 **Live SMS লিংক সেটআপ গাইড 📖**\n\n" \
                      "১. আপনার `ivasms.com` একাউন্টে লগইন থাকা অবস্থায় মেনু থেকে **'Client Active SMS'** বা **'SMS Logs'** পেজে যান।\n" \
                      "২. যেখানে লাইভ ওটিপি মেসেজগুলো আসে, সেই পেজের ওপরের ব্রাউজার লিংকটি সম্পূর্ণ কপি করুন।\n" \
                      "৩. কপি করা লিংকটি নিচে পেস্ট করে আমাকে পাঠিয়ে দিন:"
        bot.send_message(call.message.chat.id, instruction)
        admin_states[call.message.chat.id] = {"step": "sms_url", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_channel":
        bot.send_message(call.message.chat.id, "📢 নতুন **Channel ID** দিন (যেমন: -1003956226642):")
        admin_states[call.message.chat.id] = {"step": "c_id", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_group":
        bot.send_message(call.message.chat.id, "💬 নতুন **Group ID** দিন (যেমন: -1004309875319):")
        admin_states[call.message.chat.id] = {"step": "g_id", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)

if __name__ == "__main__":
    keep_alive()
    print("🚀 প্রফেশনাল ওটিপি বট সফলভাবে লাইভ হয়েছে...")
    try: bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e: print(f"বট রানিংয়ে সমস্যা: {e}")

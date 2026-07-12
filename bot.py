import telebot
import requests
import os
import time
import random
import sqlite3
import hashlib
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup

# ক্লাউডফ্লেয়ার সিকিউরিটি বাইপাস করার জন্য ক্লাউডস্ক্র্যাপার সেশন তৈরি
def create_safe_scraper():
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        print("🚀 Cloudscraper সফলভাবে চালু হয়েছে! ক্লাউডফ্লেয়ার বাইপাস একটিভ।")
        return scraper
    except Exception as e:
        print(f"⚠️ Cloudscraper লোড করা যায়নি: {e}। সাধারণ requests.Session() ব্যবহার করা হচ্ছে।")
        return requests.Session()

session = create_safe_scraper()

# ─── কনফিগারেশন ───
BOT_TOKEN = "8981181566:AAF7mng2by7JDKIJYc_7P9clBE3tINBWdkY"  # আপনার বটের টোকেনটি এখানে বসান
ADMIN_ID = 8262679678              # আপনার অ্যাডমিন আইডি ফিক্সড থাকলো

bot = telebot.TeleBot(BOT_TOKEN)
USERS_FILE = "users.txt"

app = Flask('')

@app.route('/')
def home():
    return "বট সচল আছে এবং ব্যাকগ্রাউন্ডে ওটিপি ফরোয়ার্ড করছে!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ─── SQLite ডাটাবেস হ্যান্ডলিং (৩০ সেকেন্ডের সেফ টাইমআউট সহ) ───
def init_db():
    conn = sqlite3.connect("bot_settings.db", timeout=30)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_sms (sms_hash TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS fsub_channels (chat_id TEXT PRIMARY KEY, link TEXT)''')
    
    defaults = {
        "channel_id": "-1003956226642",
        "group_id": "-1004309875319",
        "channel_link": "https://t.me/SHS_Otp_Channel",
        "group_link": "https://t.me/+DXdDIm7-rRU4YTQ1",
        "number_url": "https://www.ivasms.com/portal/numbers/test",
        "sms_url": "https://www.ivasms.com/portal/live/my_sms",
        "ivasms_email": "bdyasmin0@gmail.com",
        "ivasms_password": "1Xsahed@",
        "ivasms_cookie": "",
        "live_forward_enabled": "1"
    }
    for key, val in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (key, val))
        
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    try:
        conn = sqlite3.connect("bot_settings.db", timeout=30)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception as e:
        print(f"Database Read Error: {e}")
        return ""

def set_setting(key, value):
    try:
        conn = sqlite3.connect("bot_settings.db", timeout=30)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Write Error: {e}")

# ─── ডাইনামিক ফোর্স সাবস্ক্রিপশন ফাংশনসমূহ ───
def get_fsub_channels():
    try:
        conn = sqlite3.connect("bot_settings.db", timeout=30)
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, link FROM fsub_channels")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Database FSub Read Error: {e}")
        return []

def add_fsub_channel(chat_id, link):
    try:
        conn = sqlite3.connect("bot_settings.db", timeout=30)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO fsub_channels (chat_id, link) VALUES (?, ?)", (chat_id, link))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database FSub Write Error: {e}")

def delete_fsub_channel(chat_id):
    try:
        conn = sqlite3.connect("bot_settings.db", timeout=30)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM fsub_channels WHERE chat_id=?", (chat_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database FSub Delete Error: {e}")

def check_all_subscriptions(user_id):
    if user_id == ADMIN_ID:
        return True
    
    channels = get_fsub_channels()
    if not channels:
        return True
        
    for c_id, _ in channels:
        try:
            status = bot.get_chat_member(int(c_id), user_id).status
            if status in ['left', 'kicked']:
                return False
        except Exception as e:
            print(f"সাবস্ক্রিপশন চেক করার সময় এরর: {e}")
            return False
    return True

def send_join_request(chat_id):
    channels = get_fsub_channels()
    markup = InlineKeyboardMarkup()
    
    for i, (c_id, link) in enumerate(channels, 1):
        markup.row(InlineKeyboardButton(f"📢 Join OTP Channel {i}", url=link))
        
    markup.row(InlineKeyboardButton("✅ Joined", callback_data="check_membership"))
    bot.send_message(chat_id, "⚠️ সার্ভিসটি ব্যবহার করতে প্রথমে আমাদের ওটিপি চ্যানেল এবং গ্রুপগুলোতে জয়েন করুন। তারপর '✅ Joined' বাটনে ক্লিক করুন।", reply_markup=markup)

# ─── কোর সাবস্ক্রিপশন ও ইউজার ইন্টারফেস ফাংশনসমূহ ───
def save_user(user_id):
    try:
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, "w") as f:
                f.write(f"{user_id}\n")
        else:
            with open(USERS_FILE, "r") as f:
                users = f.read().splitlines()
            if str(user_id) not in users:
                with open(USERS_FILE, "a") as f:
                    f.write(f"{user_id}\n")
    except Exception as e:
        print(f"ইউজার ফাইল রাইট এরর: {e}")

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

def get_country_name(code):
    countries = {
        "US": "United States",
        "GB": "United Kingdom",
        "CA": "Canada",
        "FR": "France",
        "MM": "Myanmar",
        "VE": "Venezuela"
    }
    return countries.get(code.upper(), code)

# ─── IVASMS ব্যাকএন্ড ইঞ্জিন (টোকেন ও সেশন বাইপাস) ───
def login_ivasms():
    email = get_setting("ivasms_email")
    password = get_setting("ivasms_password")
    if not email or not password: return False
    
    login_url = "https://www.ivasms.com/login"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.ivasms.com/login",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    try:
        res = session.get(login_url, headers=headers, timeout=12)
        soup = BeautifulSoup(res.text, 'html.parser')
        token_input = soup.find('input', {'name': '_token'})
        csrf_token = token_input['value'] if token_input else None
        
        payload = {
            "email": email,
            "password": password
        }
        if csrf_token:
            payload["_token"] = csrf_token
            
        post_res = session.post(login_url, data=payload, headers=headers, timeout=12)
        
        if "logout" in post_res.text.lower() or "dashboard" in post_res.text.lower() or "portal" in post_res.url or post_res.status_code in [200, 302]:
            return True
    except Exception as e:
        print(f"লগইন এরর: {e}")
    return False

# সেলফ-হিলিং কুকি সেশন হ্যান্ডলার
def get_session_page(url):
    global session
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    cookie = get_setting("ivasms_cookie")
    if cookie:
        headers["Cookie"] = cookie
        
    for attempt in range(2):
        try:
            res = session.get(url, headers=headers, timeout=12)
            if "login" in res.url or ("login" in res.text.lower() and "logout" not in res.text.lower()):
                if not cookie:
                    print("সেশন শেষ! পুনরায় ব্যাকগ্রাউন্ড লগইন করা হচ্ছে...")
                    if login_ivasms():
                        res = session.get(url, headers=headers, timeout=12)
            return res
        except Exception as e:
            print(f"পেজ লোড করতে ত্রুটি (চেষ্টা {attempt+1}): {e}")
            session = create_safe_scraper()  # সেশন ক্র্যাশ করলে রিস্টার্ট করা হবে
            time.sleep(2)
    return None

def fetch_ivasms_number(country_code=None):
    url = get_setting("number_url")
    if not url: return None
    try:
        res = get_session_page(url)
        if not res: return None
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = [td.text.strip() for td in row.find_all('td')]
            if len(cols) > 1:
                for col in cols:
                    clean_num = col.replace('+', '').replace(' ', '').replace('-', '')
                    if clean_num.isdigit() and len(clean_num) >= 8:
                        row_text = row.text.lower()
                        if country_code:
                            c_name = get_country_name(country_code).lower()
                            if country_code.lower() in row_text or c_name in row_text:
                                return clean_num
                        else:
                            return clean_num
    except Exception as e:
        print(f"নম্বর ফেচ করতে ত্রুটি: {e}")
    return None

# ─── ওটিপি ফেচিং এবং ফরোয়ার্ডিং লজিক (ইউজার রিকোয়েস্ট ফেচার) ───
def poll_user_otp(chat_id, phone, selected_app):
    sms_url = get_setting("sms_url")
    if not sms_url: return
    
    for _ in range(24):
        try:
            res = get_session_page(sms_url)
            if res:
                soup = BeautifulSoup(res.text, 'html.parser')
                rows = soup.find_all('tr')
                for row in rows:
                    row_text = row.text.replace('+', '').replace(' ', '')
                    if phone in row_text:
                        cols = [td.text.strip() for td in row.find_all('td')]
                        if cols:
                            otp_message = cols[-1]
                            msg_text = f"🔥 **আপনার ওটিপি কোড এসে গেছে!** 🔥\n\n" \
                                       f"📱 অ্যাপ: #{selected_app.capitalize()}\n" \
                                       f"📞 নম্বর: `+{phone}`\n" \
                                       f"✉️ ওটিপি মেসেজ: {otp_message}"
                            
                            bot.send_message(chat_id, msg_text, parse_mode="Markdown")
                            try: bot.send_message(int(get_setting("group_id")), msg_text, parse_mode="Markdown")
                            except: pass
                            try: bot.send_message(int(get_setting("channel_id")), msg_text, parse_mode="Markdown")
                            except: pass
                            return
        except Exception as e:
            print(f"ইউজার ওটিপি ট্র্যাকিং এরর: {e}")
        time.sleep(5)

# ─── স্বয়ংক্রিয় লাইভ ওটিপি গ্রুপ ফরোয়ার্ডার ইঞ্জিন (ব্যাকগ্রাউন্ড থ্রেড) ───
def live_sms_forwarder_thread():
    while True:
        try:
            if get_setting("live_forward_enabled") == "1":
                sms_url = get_setting("sms_url")
                if sms_url:
                    res = get_session_page(sms_url)
                    if res:
                        soup = BeautifulSoup(res.text, 'html.parser')
                        rows = soup.find_all('tr')
                        
                        conn = sqlite3.connect("bot_settings.db", timeout=30)
                        cursor = conn.cursor()
                        
                        for row in rows:
                            cols = [td.text.strip() for td in row.find_all('td')]
                            if len(cols) >= 2:
                                sid = cols[0]
                                content = cols[-1]
                                
                                sms_string = f"{sid}_{content}"
                                sms_hash = hashlib.md5(sms_string.encode('utf-8')).hexdigest()
                                
                                cursor.execute("SELECT 1 FROM processed_sms WHERE sms_hash=?", (sms_hash,))
                                if not cursor.fetchone():
                                    cursor.execute("INSERT INTO processed_sms (sms_hash) VALUES (?)", (sms_hash,))
                                    conn.commit()
                                    
                                    msg_text = f"🔥 **লাইভ ওটিপি রিসিভড!** 🔥\n\n" \
                                               f"📞 প্রেরক/নম্বর: `{sid}`\n" \
                                               f"✉️ লাইভ এসএমএস: {content}"
                                               
                                    try: bot.send_message(int(get_setting("channel_id")), msg_text, parse_mode="Markdown")
                                    except: pass
                                    try: bot.send_message(int(get_setting("group_id")), msg_text, parse_mode="Markdown")
                                    except: pass
                                    
                        conn.close()
        except Exception as e:
            print(f"লাইভ এসএমএস ফরোয়ার্ডার ইঞ্জিনে ত্রুটি: {e}")
        time.sleep(12)

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
    fwd_status = "✅ Enabled" if get_setting("live_forward_enabled") == "1" else "❌ Disabled"
    
    if cookie:
        login_status = "✅ Active (Manual Cookie)"
    elif email:
        login_status = f"✅ Active (Auto: {email})"
    else:
        login_status = "❌ Not Logged In"
    
    dashboard_text = f"👑 **CONTROL DASHBOARD (অ্যাডমিন প্যানেল)**\n" \
                     f"----------------------------------------\n" \
                     f"🔐 IVASMS Status : {login_status}\n" \
                     f"📞 Numbers URL   : {num_status}\n" \
                     f"✉️ Live SMS URL : {sms_status}\n" \
                     f"📢 OTP Channel ID: `{c_id}`\n" \
                     f"💬 OTP Group ID  : `{g_id}`\n" \
                     f"🔄 Live Forward  : {fwd_status}\n" \
                     f"----------------------------------------\n" \
                     f"💡 সেটিংস কনফিগার করতে নিচের বাটনগুলো ব্যবহার করুন:"
                     
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔐 Auto Login", callback_data="adm_login"), InlineKeyboardButton("🍪 Set Cookie", callback_data="adm_cookie"))
    markup.row(InlineKeyboardButton("📞 Numbers URL", callback_data="adm_num_url"), InlineKeyboardButton("✉️ Live SMS URL", callback_data="adm_sms_url"))
    markup.row(InlineKeyboardButton("📢 Channel ID & Link", callback_data="adm_channel"), InlineKeyboardButton("💬 Group ID & Link", callback_data="adm_group"))
    markup.row(InlineKeyboardButton("➕ Add Join Channel", callback_data="adm_add_fsub"), InlineKeyboardButton("❌ Del Join Channel", callback_data="adm_del_fsub"))
    markup.row(InlineKeyboardButton("🔄 Toggle Forwarding", callback_data="adm_toggle_fwd"), InlineKeyboardButton("🔄 Refresh Panel", callback_data="adm_refresh"))
    
    if message_id:
        try: bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=dashboard_text, reply_markup=markup, parse_mode="Markdown")
        except: pass
    else:
        bot.send_message(chat_id, dashboard_text, reply_markup=markup, parse_mode="Markdown")

# ─── বটের মূল মেসেজ হ্যান্ডলারসমূহ ───

# ১. স্টার্ট কমান্ড
@bot.message_handler(commands=['start'])
def start_bot(message):
    save_user(message.chat.id)
    if not check_all_subscriptions(message.chat.id):
        send_join_request(message.chat.id)
    else:
        send_home_keyboard(message.chat.id)
        if message.chat.id == ADMIN_ID:
            send_admin_dashboard(message.chat.id)

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
            bot.reply_to(message, "✅ নোটিশ পাঠানো হয়েছে।")

# ৩. অ্যাডমিন ইনপুট প্রসেসর স্টেট মেশিন
@bot.message_handler(func=lambda msg: msg.chat.id in admin_states and msg.chat.id == ADMIN_ID)
def handle_admin_steps(message):
    try:
        state_data = admin_states[message.chat.id]
        state = state_data["step"]
        
        if state == "email":
            admin_states[message.chat.id]["email"] = message.text.strip()
            bot.reply_to(message, "🔑 এবার আপনার IVASMS পাসওয়ার্ডটি দিন:")
            admin_states[message.chat.id]["step"] = "password"
            
        elif state == "password":
            email = admin_states[message.chat.id]["email"]
            password = message.text.strip()
            set_setting("ivasms_email", email)
            set_setting("ivasms_password", password)
            status_msg = bot.reply_to(message, "⏳ IVASMS লগইন চেক করা হচ্ছে...")
            
            if login_ivasms():
                set_setting("ivasms_cookie", "")
                bot.send_message(message.chat.id, "✅ **লগইন সফল হয়েছে!**")
            else:
                set_setting("ivasms_email", "")
                set_setting("ivasms_password", "")
                bot.send_message(message.chat.id, "❌ **লগইন ব্যর্থ!** ইমেইল ও পাসওয়ার্ড পুনরায় চেক করুন।")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "cookie":
            clean_cookie = message.text.strip().replace("\n", "").replace("\r", "")
            set_setting("ivasms_cookie", clean_cookie)
            set_setting("ivasms_email", "")
            set_setting("ivasms_password", "")
            bot.reply_to(message, "✅ **কুকি সেশন সেভ হয়েছে!**")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "num_url":
            set_setting("number_url", message.text.strip())
            bot.reply_to(message, "✅ **My Numbers URL সেট হয়েছে!**")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "sms_url":
            set_setting("sms_url", message.text.strip())
            bot.reply_to(message, "✅ **Live SMS URL সেট হয়েছে!**")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "c_id":
            set_setting("channel_id", message.text.strip())
            bot.reply_to(message, "🔗 এবার নতুন ওটিপি চ্যানেল লিংকটি দিন:")
            admin_states[message.chat.id]["step"] = "c_link"
            
        elif state == "c_link":
            set_setting("channel_link", message.text.strip())
            bot.reply_to(message, "✅ ওটিপি চ্যানেল এবং জয়েনিং লিংক আপডেট হয়েছে!")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "g_id":
            set_setting("group_id", message.text.strip())
            bot.reply_to(message, "🔗 এবার নতুন ওটিপি গ্রুপ লিংকটি দিন:")
            admin_states[message.chat.id]["step"] = "g_link"
            
        elif state == "g_link":
            set_setting("group_link", message.text.strip())
            bot.reply_to(message, "✅ ওটিপি গ্রুপ এবং জয়েনিং লিংক আপডেট হয়েছে!")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
        elif state == "add_fsub_id":
            admin_states[message.chat.id]["fsub_id"] = message.text.strip()
            bot.reply_to(message, "🔗 এবার সেই চ্যানেলটির জয়েনিং লিংক (Join Link) দিন:")
            admin_states[message.chat.id]["step"] = "add_fsub_link"
            
        elif state == "add_fsub_link":
            f_id = admin_states[message.chat.id]["fsub_id"]
            f_link = message.text.strip()
            add_fsub_channel(f_id, f_link)
            bot.reply_to(message, "✅ নতুন সাবস্ক্রিপশন চ্যানেল সফলভাবে ড্যাশবোর্ডে যোগ করা হয়েছে!")
            send_admin_dashboard(message.chat.id)
            del admin_states[message.chat.id]
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ ভুল ইনপুট: {str(e)}")
        if message.chat.id in admin_states:
            del admin_states[message.chat.id]

# ৪. ইউজার কিবোর্ড বাটন কন্ট্রোল (ক্যাচ-অল)
@bot.message_handler(func=lambda message: True)
def handle_text_buttons(message):
    if not check_all_subscriptions(message.chat.id):
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
    if check_all_subscriptions(call.from_user.id):
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        send_home_keyboard(call.message.chat.id, "✅ ভেরিফিকেশন সফল হয়েছে!")
    else:
        bot.answer_callback_query(call.id, text="❌ আপনি এখনো সকল চ্যানেলে জয়েন করেননি!", show_alert=True)

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
        
    fetched_num = fetch_ivasms_number(country_code)
    
    if not fetched_num:
        bot.answer_callback_query(call.id, text="❌ এই মুহূর্তে প্যানেলে এই দেশের কোনো নম্বর ফাঁকা নেই।", show_alert=True)
        return

    msg_text = f"🌍Country ➤ {country_code}\n\n" \
               f"📞Number: `+{fetched_num}`\n\n" \
               f"⏳Status: Waiting For OTP\n" \
               f"⏰Number Validity ➤ 10 minutes\n" \
               f"🔷 ওটিপি পেতে নিচের '📥 Fetch Code' বাটনে ক্লিক করুন অথবা অটোমেটিক ওটিপির জন্য অপেক্ষা করুন।😊"
    
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
    
    Thread(target=poll_user_otp, args=(call.message.chat.id, clean_phone, selected_app)).start()

@bot.callback_query_handler(func=lambda call: call.data.startswith("fetch_"))
def manual_fetch_trigger(call):
    data_parts = call.data.split("_")
    phone = data_parts[1]
    selected_app = data_parts[2]
    
    bot.answer_callback_query(call.id, text="🔍 ওটিপি কোড খোঁজা হচ্ছে...", show_alert=False)
    poll_user_otp(call.message.chat.id, phone, selected_app)

# অ্যাডমিন প্যানেল কলব্যাক কন্ট্রোলার
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_") and call.from_user.id == ADMIN_ID)
def handle_admin_callbacks(call):
    action = call.data
    if action == "adm_refresh":
        send_admin_dashboard(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, text="🔄 ড্যাশবোর্ড আপডেট করা হয়েছে!")
        
    elif action == "adm_login":
        bot.send_message(call.message.chat.id, "📧 **IVASMS লগইন গাইড**\n\nপ্রথমে আপনার IVASMS জিমেইলটি নিচে টাইপ করে পাঠান:")
        admin_states[call.message.chat.id] = {"step": "email", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_cookie":
        instruction = "🍪 **Session Cookie সেটআপ গাইড**\n\n১. ব্রাউজারে লগইন করা অবস্থায় Cookie-Editor থেকে কুকি কপি করে এখানে পেস্ট করুন:"
        bot.send_message(call.message.chat.id, instruction)
        admin_states[call.message.chat.id] = {"step": "cookie", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_num_url":
        bot.send_message(call.message.chat.id, "📞 আপনার IVASMS-এর **Numbers/Test API URL** দিন:")
        admin_states[call.message.chat.id] = {"step": "num_url", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_sms_url":
        bot.send_message(call.message.chat.id, "✉️ আপনার IVASMS-এর **Live SMS API URL** দিন:")
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
        
    elif action == "adm_add_fsub":
        bot.send_message(call.message.chat.id, "➕ **ফোর্স সাবস্ক্রিপশন চ্যানেল যোগ:**\n\nচ্যানেল আইডি দিন (যেমন: `-10012345678`):")
        admin_states[call.message.chat.id] = {"step": "add_fsub_id", "msg_id": call.message.message_id}
        bot.answer_callback_query(call.id)
        
    elif action == "adm_del_fsub":
        channels = get_fsub_channels()
        if not channels:
            bot.answer_callback_query(call.id, text="⚠️ কোনো সাবস্ক্রিপশন চ্যানেল যোগ করা নেই!", show_alert=True)
            return
        markup = InlineKeyboardMarkup()
        for c_id, link in channels:
            markup.row(InlineKeyboardButton(f"❌ Del: {c_id}", callback_data=f"fsubdel_{c_id}"))
        markup.row(InlineKeyboardButton("⬅️ Back", callback_data="adm_refresh"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="❌ **ডিলিট করার জন্য নিচের জয়েন চ্যানেলটি সিলেক্ট করুন:**", reply_markup=markup)
        bot.answer_callback_query(call.id)
        
    elif action == "adm_toggle_fwd":
        current = get_setting("live_forward_enabled")
        new_val = "0" if current == "1" else "1"
        set_setting("live_forward_enabled", new_val)
        send_admin_dashboard(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, text=f"🔄 ফরোয়ার্ডিং {'সচল' if new_val=='1' else 'বন্ধ'} করা হয়েছে!")

# ডায়নামিক ফোর্স সাবস্ক্রিপশন ডিলিট অ্যাকশন
@bot.callback_query_handler(func=lambda call: call.data.startswith("fsubdel_") and call.from_user.id == ADMIN_ID)
def handle_fsub_delete(call):
    c_id = call.data.replace("fsubdel_", "")
    delete_fsub_channel(c_id)
    bot.answer_callback_query(call.id, text="✅ চ্যানেলটি সফলভাবে ডিলিট করা হয়েছে!")
    send_admin_dashboard(call.message.chat.id, call.message.message_id)

if __name__ == "__main__":
    keep_alive()
    Thread(target=live_sms_forwarder_thread, daemon=True).start()
    print("🚀 প্রফেশনাল ওটিপি বট সফলভাবে লাইভ হয়েছে...")
    
    # ইনফিনিট পোলিং লুপ (সাময়িক ক্র্যাশেও বট বন্ধ হবে না)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=25)
        except Exception as e:
            print(f"বট রানিংয়ে সাময়িক সমস্যা, ৫ সেকেন্ড পর অটো-রিস্টার্ট হচ্ছে: {e}")
            time.sleep(5)

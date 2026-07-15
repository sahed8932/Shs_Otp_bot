import telebot
import requests
import os
import time
import json
import hashlib
import collections
import re
from datetime import datetime
from telebot import types
from flask import Flask
from threading import Thread

# ==================== CONFIGURATION ZONE ====================
# এখানে আপনার বটের টোকেন, এপিআই কী এবং গ্রুপ আইডিগুলো পরিবর্তন করে নিন
BOT_TOKEN = "8981181566:AAF7mng2by7JDKIJYc_7P9clBE3tINBWdkY"
API_KEY = "MCZJ7C79228"                  # আপনার VoltX SMS API Key এখানে বসাবেন
ADMIN_ID = 8262679678                   # আপনার অ্যাডমিন আইডি
WHATSAPP_ONLY_GROUP = "-1003956226642"  # শুধুমাত্র হোয়াটসঅ্যাপ-এর ওটিপি পাঠানোর গ্রুপ আইডি
ALL_SERVICES_GROUP = "-1004309875319"   # ফেসবুক ও অল সার্ভিস ওটিপি পাঠানোর গ্রুপ আইডি
# ============================================================

CONFIG_FILE = "config.json"
USERS_FILE = "users.json"

# ডুপ্লিকেট মেসেজ প্রতিরোধে মেমোরি ক্যাশ (সর্বোচ্চ ৩০০টি মেসেজ ট্র্যাক করবে)
forwarded_hashes = collections.deque(maxlen=300)

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_users(users_set):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users_set), f)

def load_config():
    # ফাইল থেকে পুরনো ডাটা লোড করার চেষ্টা করা হচ্ছে
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
        except:
            cfg = {}
    else:
        cfg = {}

    # CONFIGURATION ZONE-এর ডাটা দিয়ে সবসময় ক্যাশ আপডেট করা হবে (নতুন এডিট কার্যকর করার জন্য)
    cfg["BOT_TOKEN"] = BOT_TOKEN
    cfg["FASTX_API_KEY"] = API_KEY
    cfg["ADMIN_ID"] = ADMIN_ID
    cfg["WHATSAPP_ONLY_GROUP"] = WHATSAPP_ONLY_GROUP
    cfg["ALL_SERVICES_GROUP"] = ALL_SERVICES_GROUP
    
    # অন্যান্য ডিফল্ট প্যারামিটার সেট করা হচ্ছে
    if "BASE_URL" not in cfg:
        cfg["BASE_URL"] = "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api"
    if "BOT_NAME" not in cfg:
        cfg["BOT_NAME"] = "Volt X SMS BOT"
    if "BOT_USERNAME" not in cfg:
        cfg["BOT_USERNAME"] = "ShsOtp_bot"
    if "DEV_USERNAME" not in cfg:
        cfg["DEV_USERNAME"] = "Saku_143"
    if "RANGE_GROUP_LINK" not in cfg:
        cfg["RANGE_GROUP_LINK"] = "https://t.me/SHS_Otp_Channel"
    if "SUPPORT_LINK" not in cfg:
        cfg["SUPPORT_LINK"] = "https://t.me/Saku_143"
    if "CHANNELS_TO_JOIN" not in cfg:
        cfg["CHANNELS_TO_JOIN"] = [
            {"id": "-1003956226642", "link": "https://t.me/SHS_Otp_Channel", "name": "📢 Otp Channel"},
            {"id": "-1002183552076", "link": "https://t.me/winfanti", "name": "💬 Support Channel"}
        ]
    if "GROUPS_TO_JOIN" not in cfg:
        cfg["GROUPS_TO_JOIN"] = [
            {"id": "-1004309875319", "link": "https://t.me/+DXdDIm7-rRU4YTQ1", "name": "👥 OTP Support Group"}
        ]
    if "NOTICE" not in cfg:
        cfg["NOTICE"] = "⚠️ সার্ভিসটি ফুল স্পিডে সচল রয়েছে। কোনো সমস্যা হলে গ্রুপে জানান।"

    save_config(cfg)
    return cfg

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

config = load_config()
bot = telebot.TeleBot(config["BOT_TOKEN"])
app = Flask('')
all_users = load_users()

@app.route('/')
def home(): return "VoltX SMS OTP Bot is Live & Active!"

def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): Thread(target=run).start()

def track_user(user_id):
    global all_users
    if user_id not in all_users:
        all_users.add(user_id)
        save_users(all_users)

def is_subscribed_all(user_id):
    if user_id == int(config["ADMIN_ID"]): return True 
    for ch in config.get("CHANNELS_TO_JOIN", []):
        try:
            status = bot.get_chat_member(int(ch["id"]), user_id).status
            if status in ['left', 'kicked', 'restricted']: return False
        except: pass 
    for grp in config.get("GROUPS_TO_JOIN", []):
        try:
            status = bot.get_chat_member(int(grp["id"]), user_id).status
            if status in ['left', 'kicked', 'restricted']: return False
        except: pass
    return True

def get_api_headers():
    return {"mauthapi": str(config.get("FASTX_API_KEY", "")).strip()}

def safe_int(val):
    try:
        return int(str(val).strip())
    except:
        return None

def parse_api_data(res_json):
    """
    প্যানেল থেকে আগত এপিআই ডাটা ডিকশনারি বা সরাসরি লিস্ট আকারে থাকলেও তা ক্র্যাশ না করে নিরাপদে এক্সট্রাক্ট করবে
    """
    data_obj = res_json.get("data")
    if not data_obj:
        return []
    if isinstance(data_obj, list):
        return data_obj
    if isinstance(data_obj, dict):
        for k, v in data_obj.items():
            if isinstance(v, list):
                return v
    return []

def send_home_keyboard(chat_id, text=None):
    track_user(chat_id)
    if not text:
        text = f"👋 ওটিপি ড্যাশবোর্ডে স্বাগতম!\n\n📢 **নোটিশ:** {config.get('NOTICE', 'কোনো নোটিশ নেই')}"
        
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🛍️ GET NUMBER"), types.KeyboardButton("📊 View Range"))
    markup.row(types.KeyboardButton("🧑‍💻 Support"))
    if chat_id == int(config["ADMIN_ID"]):
        markup.row(types.KeyboardButton("🛠 Admin Dashboard"))
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

def format_active_range_card(service, country, key_code, range_id, time_str, message_body):
    service_lower = str(service).lower()
    if "facebook" in service_lower:
        emoji = "📸✨"
        serv_title = "FACEBOOK RANGE"
    elif "whatsapp" in service_lower:
        emoji = "💚✨"
        serv_title = "WHATSAPP RANGE"
    elif "telegram" in service_lower:
        emoji = "✈️✨"
        serv_title = "TELEGRAM RANGE"
    elif "imo" in service_lower:
        emoji = "📱✨"
        serv_title = "IMO RANGE"
    elif "instagram" in service_lower:
        emoji = "📸✨"
        serv_title = "INSTAGRAM RANGE"
    elif "tiktok" in service_lower:
        emoji = "🎵✨"
        serv_title = "TIKTOK RANGE"
    else:
        emoji = "🌐✨"
        serv_title = f"{str(service).upper()} RANGE"

    card_text = (
        f"ACTIVE RANGE\n"
        f"╭───────────────╮\n"
        f"{emoji} {serv_title} ✨\n"
        f"╰───────────────╯\n\n"
        f"🌐 Country  ➔ {country}\n"
        f"🗣️ Service ➔ {str(service).capitalize()}\n"
        f"🔐 Key ➔ {key_code}\n\n"
        f"🎯 Range    ➔ {range_id}\n\n"
        f"🕒 Time     ➔ {time_str}\n\n"
        f"✉️ Message\n"
        f"{message_body}"
    )
    return card_text

@bot.message_handler(commands=['start'])
def start_bot(message):
    track_user(message.chat.id)
    if is_subscribed_all(message.chat.id):
        send_home_keyboard(message.chat.id)
    else:
        markup = types.InlineKeyboardMarkup()
        for ch in config.get("CHANNELS_TO_JOIN", []):
            markup.row(types.InlineKeyboardButton(ch["name"], url=ch["link"]))
        for grp in config.get("GROUPS_TO_JOIN", []):
            markup.row(types.InlineKeyboardButton(grp["name"], url=grp["link"]))
        markup.row(types.InlineKeyboardButton("✅ Joined (Check)", callback_data="check_membership"))
        bot.send_message(message.chat.id, "⚠️ সার্ভিসটি ব্যবহার করতে নিচের সমস্ত চ্যানেল এবং গ্রুপগুলোতে অবশ্যই জয়েন করুন, এরপর 'Joined' বাটনে ক্লিক করুন।", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    track_user(message.chat.id)
    if not is_subscribed_all(message.chat.id):
        markup = types.InlineKeyboardMarkup()
        for ch in config.get("CHANNELS_TO_JOIN", []):
            markup.row(types.InlineKeyboardButton(ch["name"], url=ch["link"]))
        for grp in config.get("GROUPS_TO_JOIN", []):
            markup.row(types.InlineKeyboardButton(grp["name"], url=grp["link"]))
        markup.row(types.InlineKeyboardButton("✅ Joined (Check)", callback_data="check_membership"))
        bot.send_message(message.chat.id, "❌ আপনি এখনো সমস্ত চ্যানেল বা গ্রুপে জয়েন করেননি!\n\nদয়া করে উপরের সমস্ত চ্যানেল ও গ্রুপগুলোতে জয়েন করুন, এরপর নিচের **Joined** বাটনে ক্লিক করুন।", reply_markup=markup)
        return
    
    text = message.text
    if text == "🛍️ GET NUMBER":
        msg = bot.send_message(message.chat.id, "⌨️ Enter Range ID (e.g., 123456XXX):")
        bot.register_next_step_handler(msg, process_get_number_by_range)
        
    elif text == "📊 View Range":
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📊 Live access", callback_data="view_live_access"),
            types.InlineKeyboardButton("🔗 Range Group", url=config.get("RANGE_GROUP_LINK", "https://t.me/SHS_Otp_Channel"))
        )
        bot.send_message(message.chat.id, "📌 Click the button below to view active ranges:", reply_markup=markup)
        
    elif text == "🧑‍💻 Support":
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🤷‍♂️ Support", url=config.get("SUPPORT_LINK", "https://t.me/Saku_143")))
        bot.send_message(message.chat.id, "আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করতে নিচের বাটনে ক্লিক করুন:", reply_markup=markup)
        
    elif text == "🛠 Admin Dashboard" and message.chat.id == int(config["ADMIN_ID"]):
        show_admin_dashboard(message.chat.id)

def process_get_number_by_range(message):
    chat_id = message.chat.id
    range_id = message.text.strip().upper().replace("XXX", "")
    
    if not range_id:
        bot.send_message(chat_id, "❌ রেঞ্জ আইডি সঠিক নয়। অনুগ্রহ করে পুনরায় চেষ্টা করুন।")
        return
        
    status_msg = bot.send_message(chat_id, "🔍 নম্বর বরাদ্দ করা হচ্ছে, দয়া করে অপেক্ষা করুন...")
    
    base_url = str(config['BASE_URL']).strip().rstrip('/')
    url = f"{base_url}/getnum"
    payload = {"rid": str(range_id)}
    
    try:
        response = requests.post(url, json=payload, headers=get_api_headers(), timeout=20)
        res = response.json()
        meta = res.get("meta", {})
        
        if meta.get("status") == "ok" or meta.get("code") == 200:
            data = res.get("data", {})
            num = data.get("full_number") or data.get("number") or data.get("phone") or data.get("no_plus_number")
            
            if not num:
                bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ সার্ভার নম্বর ফেরত দিতে পারেনি। অনুগ্রহ করে আবার চেষ্টা করুন।")
                return
                
            msg = (f"✅ **Number Assigned Successfully!**\n\n"
                   f"📱 Range ID ➔ `{range_id}`\n"
                   f"📞 Number: `{num}`\n\n"
                   f"⏳ Status: Waiting For OTP\n"
                   f"⏰ Validity ➔ 10 minutes\n\n"
                   f"💎 নিচে 'Fetch Code' বাটনে ক্লিক করে বা অটো ওটিপির জন্য অপেক্ষা করুন।")
            
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("📥 Fetch Code", callback_data=f"fetch_{range_id}_{num}"),
                types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_{range_id}")
            )
            markup.row(types.InlineKeyboardButton("📋 Copy Number", callback_data=f"copynum_{num}"))
            markup.row(types.InlineKeyboardButton("🔗 View OTP Group", url=config.get("RANGE_GROUP_LINK", "https://t.me/SHS_Otp_Channel")))
            
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=msg, reply_markup=markup, parse_mode="Markdown")
            
            # ব্যাকগ্রাউন্ড ওটিপি ওয়াচার চালু
            Thread(target=background_user_otp_watcher, args=(chat_id, status_msg.message_id, range_id, num), daemon=True).start()
        else:
            err_msg = res.get("message") or "নম্বর স্টক শেষ অথবা রেঞ্জ আইডি ভুল!"
            bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"❌ প্যানেল এরর: {err_msg}")
    except Exception as e:
        bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="⚠️ কানেকশন সমস্যা! অনুগ্রহ করে আবার চেষ্টা করুন।")

@bot.callback_query_handler(func=lambda call: call.data.startswith("change_"))
def callback_change_number(call):
    range_id = call.data.split("_")[1]
    bot.answer_callback_query(call.id, text="🔄 নতুন নাম্বার নেওয়া হচ্ছে...")
    
    class MockMessage:
        def __init__(self, chat, text):
            self.chat = chat
            self.text = text
            
    mock_msg = MockMessage(call.message.chat, range_id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    process_get_number_by_range(mock_msg)

@bot.callback_query_handler(func=lambda call: call.data.startswith("fetch_"))
def callback_manual_fetch(call):
    parts = call.data.split("_")
    range_id = parts[1]
    num = parts[2]
    bot.answer_callback_query(call.id, text="🔍 ওটিপি চেক করা হচ্ছে...")
    
    found = check_and_send_user_otp(call.message.chat.id, range_id, num)
    if not found:
        bot.send_message(call.message.chat.id, "⚠️ ওটিপি এখনও প্যানেলে আসেনি। একটু পরে আবার চেষ্টা করুন।")

def check_and_send_user_otp(chat_id, range_id, num):
    base_url = str(config['BASE_URL']).strip().rstrip('/')
    url = f"{base_url}/success-otp"
    
    try:
        response = requests.get(url, headers=get_api_headers(), timeout=15)
        if response.status_code != 200:
            return False
            
        res = response.json()
        if res.get("meta", {}).get("status") == "ok":
            otps_list = parse_api_data(res)
            clean_num = str(num).replace("+", "").strip()
            
            found_item = None
            for item in otps_list:
                item_num = str(item.get("number")).replace("+", "").strip()
                if item_num == clean_num or clean_num.endswith(item_num) or item_num.endswith(clean_num):
                    found_item = item
                    break
                    
            if found_item:
                otp_code = found_item.get("otp") or found_item.get("code")
                msg_body = found_item.get("message") or found_item.get("sms") or ""
                service = found_item.get("service") or found_item.get("platform") or found_item.get("sid") or "Unknown"
                country = found_item.get("country", "Global")
                time_val = found_item.get("time")
                
                # যদি টাইমস্ট্যাম্প Epoch হয় তবে রিডেবল ফরম্যাটে কনভার্ট করবে
                if isinstance(time_val, (int, float)):
                    if time_val > 5000000000:
                        time_val = time_val / 1000
                    try:
                        time_str = datetime.fromtimestamp(time_val).strftime("%Y-%m-%d %I:%M:%S %p")
                    except:
                        time_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                else:
                    time_str = str(time_val) if time_val else datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                
                if not otp_code:
                    code_match = re.search(r'\b\d{4,8}\b', msg_body)
                    otp_code = code_match.group(0) if code_match else "N/A"
                    
                formatted_card = format_active_range_card(
                    service=service,
                    country=country,
                    key_code=otp_code,
                    range_id=range_id,
                    time_str=time_str,
                    message_body=msg_body
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("📋 Copy OTP", callback_data=f"copyotp_{otp_code}"),
                    types.InlineKeyboardButton("📞 Copy Number", callback_data=f"copynum_{num}")
                )
                
                bot.send_message(chat_id, formatted_card, reply_markup=markup, parse_mode="Markdown")
                
                # লাইভ গ্রুপসমূহে ফরওয়ার্ড করার লজিক (MD5 ডুপ্লিকেট চেকিং সহ)
                unique_str = f"{num}_{otp_code}_{msg_body[:30]}"
                h = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
                if h not in forwarded_hashes:
                    forwarded_hashes.append(h)
                    
                    service_lower = str(service).lower()
                    group_markup = types.InlineKeyboardMarkup()
                    group_markup.row(
                        types.InlineKeyboardButton("📋 Copy OTP", callback_data=f"copyotp_{otp_code}"),
                        types.InlineKeyboardButton("📞 Copy Number", callback_data=f"copynum_{num}")
                    )
                    group_markup.row(
                        types.InlineKeyboardButton("👑 Owner", url=f"https://t.me/{config.get('DEV_USERNAME', 'Saku_143')}"),
                        types.InlineKeyboardButton("📱 Bot", url=f"https://t.me/{config.get('BOT_USERNAME', 'SHS_SMSHUB_bot')}")
                    )
                    
                    if "whatsapp" in service_lower:
                        dest_group_id = safe_int(config.get("WHATSAPP_ONLY_GROUP"))
                        if dest_group_id:
                            try: bot.send_message(dest_group_id, formatted_card, reply_markup=group_markup, parse_mode="Markdown")
                            except: pass
                    else:
                        dest_group_id = safe_int(config.get("ALL_SERVICES_GROUP"))
                        if dest_group_id:
                            try: bot.send_message(dest_group_id, formatted_card, reply_markup=group_markup, parse_mode="Markdown")
                            except: pass
                
                return True
    except Exception as e:
        print(f"Error in manual check: {e}")
    return False

def background_user_otp_watcher(chat_id, message_id, range_id, num):
    checks = 0
    while checks < 40:
        time.sleep(15)
        checks += 1
        found = check_and_send_user_otp(chat_id, range_id, num)
        if found:
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ **OTP Received Successfully!**\n\n📞 Number: `{num}`\n\n ওটিপি নিচে চলে এসেছে বা আপনার গ্রুপে ফরোয়ার্ড করা হয়েছে।",
                    parse_mode="Markdown"
                )
            except:
                pass
            break

@bot.callback_query_handler(func=lambda call: call.data == "view_live_access")
def callback_view_live_access(call):
    bot.answer_callback_query(call.id, text="🔍 লোড করা হচ্ছে...")
    
    base_url = str(config['BASE_URL']).strip().rstrip('/')
    url = f"{base_url}/liveaccess"
    try:
        response = requests.get(url, headers=get_api_headers(), timeout=15)
        res = response.json()
        if res.get("meta", {}).get("status") == "ok":
            data_list = parse_api_data(res)
            if not data_list:
                bot.send_message(call.message.chat.id, "📊 **বর্তমানে কোনো অ্যাক্টিভ রেঞ্জ পাওয়া যায়নি।**", parse_mode="Markdown")
                return
            
            msg = "📊 **Active Ranges & Live Access:**\n\n"
            for item in data_list:
                service = (item.get("service") or item.get("platform") or item.get("sid") or "Unknown").upper()
                ranges = item.get("ranges", [])
                ranges_str = ", ".join([f"`{r}`" for r in ranges])
                msg += f"📱 **{service}** ➔ {ranges_str}\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("⬅️ Back", callback_data="back_view_range"))
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=msg, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, "📊 Active Traffic: সার্ভার রানিং আছে!")
    except Exception as e:
        bot.send_message(call.message.chat.id, "📊 Active Traffic: সার্ভার রানিং আছে! (API কানেকশনে সমস্যা)")

@bot.callback_query_handler(func=lambda call: call.data == "back_view_range")
def back_view_range(call):
    try:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📊 Live access", callback_data="view_live_access"),
            types.InlineKeyboardButton("🔗 Range Group", url=config.get("RANGE_GROUP_LINK", "https://t.me/SHS_Otp_Channel"))
        )
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="📌 Click the button below to view active ranges:", reply_markup=markup)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("copynum_"))
def copy_number_alert(call):
    num = call.data.split("_")[1]
    bot.answer_callback_query(call.id, text=f"📞 Number: {num}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copyotp_"))
def copy_otp_alert(call):
    code = call.data.split("_")[1]
    bot.answer_callback_query(call.id, text=f"🔐 OTP Code: {code}", show_alert=True)

def background_live_sms_monitor():
    """প্যানেলের গ্লোবাল লাইভ কনসোল থেকে রিয়েল-টাইম ডাটা ফেচ করে ফিল্টার অনুযায়ী গ্রুপে পাঠাবে"""
    while True:
        try:
            time.sleep(6)  # সার্ভার ক্যাশ ৫ সেকেন্ড, তাই প্রতি ৬ সেকেন্ডে চেক করা হবে
            base_url = str(config['BASE_URL']).strip().rstrip('/')
            url = f"{base_url}/console"
            
            response = requests.get(url, headers=get_api_headers(), timeout=15)
            if response.status_code != 200:
                continue
                
            res = response.json()
            if res.get("meta", {}).get("status") == "ok":
                otps_list = parse_api_data(res)
                if not isinstance(otps_list, list):
                    continue
                
                for item in otps_list:
                    if not isinstance(item, dict):
                        continue
                    num = item.get("number")
                    otp_code = item.get("otp") or item.get("code")
                    msg_body = item.get("message") or item.get("sms") or ""
                    service = item.get("service") or item.get("platform") or item.get("sid") or "unknown"
                    country = item.get("country", "Global")
                    range_id = item.get("range", "N/A")
                    time_val = item.get("time")
                    
                    # Epoch কনভার্ট
                    if isinstance(time_val, (int, float)):
                        if time_val > 5000000000:
                            time_val = time_val / 1000
                        try:
                            time_str = datetime.fromtimestamp(time_val).strftime("%Y-%m-%d %I:%M:%S %p")
                        except:
                            time_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                    else:
                        time_str = str(time_val) if time_val else datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                    
                    if not num or not msg_body:
                        continue
                        
                    # ইউনিক MD5 হ্যাশ চেকিং ডুপ্লিকেট রোধের জন্য
                    unique_str = f"{num}_{otp_code}_{msg_body[:30]}"
                    h = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
                    if h in forwarded_hashes:
                        continue
                    forwarded_hashes.append(h)
                    
                    if not otp_code:
                        code_match = re.search(r'\b\d{4,8}\b', msg_body)
                        otp_code = code_match.group(0) if code_match else "N/A"
                        
                    formatted_card = format_active_range_card(
                        service=service,
                        country=country,
                        key_code=otp_code,
                        range_id=range_id,
                        time_str=time_str,
                        message_body=msg_body
                    )
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.row(
                        types.InlineKeyboardButton("📋 Copy OTP", callback_data=f"copyotp_{otp_code}"),
                        types.InlineKeyboardButton("📞 Copy Number", callback_data=f"copynum_{num}")
                    )
                    markup.row(
                        types.InlineKeyboardButton("👑 Owner", url=f"https://t.me/{config.get('DEV_USERNAME', 'Saku_143')}"),
                        types.InlineKeyboardButton("📱 Bot", url=f"https://t.me/{config.get('BOT_USERNAME', 'SHS_SMSHUB_bot')}")
                    )
                    
                    service_lower = str(service).lower()
                    
                    # ডুয়াল ফরওয়ার্ডিং সিস্টেম (গ্রুপে ভাগ করা)
                    if "whatsapp" in service_lower:
                        dest_group_id = safe_int(config.get("WHATSAPP_ONLY_GROUP"))
                        if dest_group_id:
                            try:
                                bot.send_message(dest_group_id, formatted_card, reply_markup=markup, parse_mode="Markdown")
                            except Exception as ex:
                                print(f"WhatsApp forward error: {ex}")
                    else:
                        dest_group_id = safe_int(config.get("ALL_SERVICES_GROUP"))
                        if dest_group_id:
                            try:
                                bot.send_message(dest_group_id, formatted_card, reply_markup=markup, parse_mode="Markdown")
                            except Exception as ex:
                                print(f"All services forward error: {ex}")
                                
        except Exception as e:
            time.sleep(6)

def show_admin_dashboard(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("📢 Manage Channels/Groups", callback_data="adm_channels"))
    markup.row(types.InlineKeyboardButton("📢 Broadcast Message", callback_data="adm_broadcast"))
    markup.row(types.InlineKeyboardButton("✍️ Set Notice", callback_data="adm_setnotice"),
               types.InlineKeyboardButton("🤖 Set Bot Name", callback_data="adm_setname"))
    markup.row(types.InlineKeyboardButton("🔗 Set Bot Username", callback_data="adm_setbotuser"),
               types.InlineKeyboardButton("👨‍💻 Set Dev Username", callback_data="adm_setdevuser"))
    markup.row(types.InlineKeyboardButton("🔑 Update API Key", callback_data="adm_setkey"))
    markup.row(types.InlineKeyboardButton("🟢 Set WA Group ID", callback_data="adm_setwagrp"),
               types.InlineKeyboardButton("🔵 Set All Group ID", callback_data="adm_setallgrp"))
    
    bot_title = config.get("BOT_NAME", "Quick X SMS BOT")
    bot_user = config.get("BOT_USERNAME", "SHS_SMSHUB_bot")
    dev_user = config.get("DEV_USERNAME", "Saku_143")
    
    text = (f"🛠 **অ্যাডমিন কন্ট্রোল প্যানেল (VoltX OTP)**\n\n"
            f"• Bot Name: `{bot_title}`\n"
            f"• Bot Username: `@{bot_user}`\n"
            f"• Dev Username: `@{dev_user}`\n"
            f"• Total Users: `{len(all_users)}`\n"
            f"• API Key: `{config.get('FASTX_API_KEY', '')}`\n"
            f"• WA Group ID: `{config.get('WHATSAPP_ONLY_GROUP', 'None')}`\n"
            f"• All Group ID: `{config.get('ALL_SERVICES_GROUP', 'None')}`\n"
            f"• বর্তমান নোটিশ: {config.get('NOTICE', 'নেই')}")
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def handle_admin_callbacks(call):
    if call.message.chat.id != int(config["ADMIN_ID"]): return
    data = call.data
    chat_id = call.message.chat.id
    
    if data == "adm_channels":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ নতুন চ্যানেল/গ্রুপ অ্যাড করুন", callback_data="ch_add"))
        markup.add(types.InlineKeyboardButton("🗑 চ্যানেল/গ্রুপ রিমুভ করুন", callback_data="ch_remove"))
        markup.add(types.InlineKeyboardButton("⬅️ ব্যাক", callback_data="adm_back"))
        
        c_list = "\n".join([f"📢 {c['name']} (`{c['id']}`)" for c in config["CHANNELS_TO_JOIN"]])
        g_list = "\n".join([f"👥 {g['name']} (`{g['id']}`)" for g in config["GROUPS_TO_JOIN"]])
        text = f"📢 **চ্যানেল ও গ্রুপ ম্যানেজমেন্ট**\n\n**বর্তমান চ্যানেলসমূহ:**\n{c_list}\n\n**বর্তমান গ্রুপসমূহ:**\n{g_list}"
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=markup, parse_mode="Markdown")

    elif data == "adm_broadcast":
        msg = bot.send_message(chat_id, "📢 আপনি সকল ইউজারদের কাছে যে মেসেজটি পাঠাতে চান তা লিখে বা ফরোয়ার্ড করে পাঠান:")
        bot.register_next_step_handler(msg, process_broadcast)
    elif data == "adm_setnotice":
        msg = bot.send_message(chat_id, "👉 ইউজারদের জন্য নতুন নোটিশটি লিখে পাঠান:")
        bot.register_next_step_handler(msg, save_notice)
    elif data == "adm_setname":
        msg = bot.send_message(chat_id, "👉 নতুন বটের নাম লিখে পাঠান:")
        bot.register_next_step_handler(msg, save_bot_name)
    elif data == "adm_setbotuser":
        msg = bot.send_message(chat_id, "👉 বটের ইউজারনেম লিখুন (@ ছাড়া):")
        bot.register_next_step_handler(msg, save_bot_username)
    elif data == "adm_setdevuser":
        msg = bot.send_message(chat_id, "👉 ডেভেলপার ইউজারনেম লিখুন (@ ছাড়া):")
        bot.register_next_step_handler(msg, save_dev_username)
    elif data == "adm_setkey":
        msg = bot.send_message(chat_id, "👉 আপনার নতুন VoltX SMS API Key টি পাঠান:")
        bot.register_next_step_handler(msg, save_api_key)
    elif data == "adm_setwagrp":
        msg = bot.send_message(chat_id, "👉 হোয়াটসঅ্যাপ এর লাইভ ওটিপি পাঠানোর জন্য গ্রুপ আইডিটি পাঠান (যেমন: `-100xxxxxx`):")
        bot.register_next_step_handler(msg, save_wa_group_id)
    elif data == "adm_setallgrp":
        msg = bot.send_message(chat_id, "👉 ফেসবুক এবং সকল রেঞ্জের ওটিপি পাঠানোর জন্য গ্রুপ আইডিটি পাঠান (যেমন: `-100xxxxxx`):")
        bot.register_next_step_handler(msg, save_all_group_id)
    elif data == "adm_back":
        show_admin_dashboard(chat_id)

def save_wa_group_id(message):
    config["WHATSAPP_ONLY_GROUP"] = message.text.strip()
    save_config(config)
    bot.send_message(message.chat.id, "✅ হোয়াটসঅ্যাপ লাইভ ওটিপি গ্রুপ আইডি আপডেট হয়েছে।")
    show_admin_dashboard(message.chat.id)

def save_all_group_id(message):
    config["ALL_SERVICES_GROUP"] = message.text.strip()
    save_config(config)
    bot.send_message(message.chat.id, "✅ ফেসবুক এবং সকল ওটিপি গ্রুপ আইডি আপডেট হয়েছে।")
    show_admin_dashboard(message.chat.id)

def process_broadcast(message):
    chat_id = message.chat.id
    success = 0
    failed = 0
    status_msg = bot.send_message(chat_id, "🚀 ব্রডকাস্ট শুরু হয়েছে, দয়া করে অপেক্ষা করুন...")
    
    for uid in list(all_users):
        try:
            bot.copy_message(chat_id=int(uid), from_chat_id=chat_id, message_id=message.message_id)
            success += 1
            time.sleep(0.1)
        except:
            failed += 1
            
    bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, 
                          text=f"✅ ব্রডকাস্ট সম্পন্ন!\n\n• সফলভাবে পাঠানো হয়েছে: `{success}` জনের কাছে\n• ফেইল হয়েছে: `{failed}` জনের কাছে", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "ch_add")
def wizard_add_channel(call):
    msg = bot.send_message(call.message.chat.id, "👉 নতুন চ্যানেল বা গ্রুপ যুক্ত করতে এভাবে লিখে পাঠান:\n\n`টাইপ আইডি লিংক নাম`\n\n*উদাহরণ:* `channel -100123456789 https://t.me/mychannel MyChannel`")
    bot.register_next_step_handler(msg, process_save_channel_group)

def process_save_channel_group(message):
    try:
        parts = message.text.strip().split(maxsplit=3)
        ch_type = parts[0].lower()
        ch_id = parts[1]
        ch_link = parts[2]
        ch_name = parts[3]
        item = {"id": ch_id, "link": ch_link, "name": ch_name}
        if ch_type == "channel":
            config["CHANNELS_TO_JOIN"].append(item)
        elif ch_type == "group":
            config["GROUPS_TO_JOIN"].append(item)
        save_config(config)
        bot.send_message(message.chat.id, "✅ সফলভাবে চ্যানেল/গ্রুপ যুক্ত করা হয়েছে!")
    except:
        bot.send_message(message.chat.id, "❌ ফরম্যাট সঠিক নয়! আবার চেষ্টা করুন।")
    show_admin_dashboard(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "ch_remove")
def wizard_remove_channel(call):
    markup = types.InlineKeyboardMarkup()
    for idx, c in enumerate(config["CHANNELS_TO_JOIN"]):
        markup.add(types.InlineKeyboardButton(f"❌ চ্যানেল ডিলিট: {c['name']}", callback_data=f"delch_c_{idx}"))
    for idx, g in enumerate(config["GROUPS_TO_JOIN"]):
        markup.add(types.InlineKeyboardButton(f"❌ গ্রুপ ডিলিট: {g['name']}", callback_data=f"delch_g_{idx}"))
    markup.add(types.InlineKeyboardButton("⬅️ ব্যাক", callback_data="adm_channels"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="🗑 যে চ্যানেল বা গ্রুপটি রিমুভ করতে চান তাতে ক্লিক করুন:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delch_"))
def execute_remove_channel(call):
    _, target_type, idx_str = call.data.split("_")
    idx = int(idx_str)
    if target_type == "c" and len(config["CHANNELS_TO_JOIN"]) > 1:
        config["CHANNELS_TO_JOIN"].pop(idx)
        save_config(config)
        bot.answer_callback_query(call.id, text="✅ চ্যানেল রিমুভ হয়েছে!", show_alert=True)
    elif target_type == "g":
        config["GROUPS_TO_JOIN"].pop(idx)
        save_config(config)
        bot.answer_callback_query(call.id, text="✅ গ্রুপ রিমুভ হয়েছে!", show_alert=True)
    show_admin_dashboard(call.message.chat.id)

def save_notice(message):
    config["NOTICE"] = message.text.strip()
    save_config(config)
    bot.send_message(message.chat.id, "✅ নোটিশ আপডেট হয়েছে।")
    show_admin_dashboard(message.chat.id)

def save_bot_name(message):
    config["BOT_NAME"] = message.text.strip()
    save_config(config)
    bot.send_message(message.chat.id, "✅ বটের নাম আপডেট হয়েছে।")
    show_admin_dashboard(message.chat.id)

def save_bot_username(message):
    config["BOT_USERNAME"] = message.text.strip().replace("@", "")
    save_config(config)
    bot.send_message(message.chat.id, "✅ বটের ইউজারনেম আপডেট হয়েছে।")
    show_admin_dashboard(message.chat.id)

def save_dev_username(message):
    config["DEV_USERNAME"] = message.text.strip().replace("@", "")
    save_config(config)
    bot.send_message(message.chat.id, "✅ ডেভেলপার ইউজারনেম আপডেট হয়েছে।")
    show_admin_dashboard(message.chat.id)

def save_api_key(message):
    config["FASTX_API_KEY"] = message.text.strip()
    save_config(config)
    bot.send_message(message.chat.id, "✅ API Key আপডেট হয়েছে।")
    show_admin_dashboard(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check(call):
    if is_subscribed_all(call.from_user.id): 
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        send_home_keyboard(call.message.chat.id, "✅ ভেরিфикации সফল! এখন থেকে সার্ভিস ব্যবহার করতে পারবেন।")
    else: 
        bot.answer_callback_query(call.id, text="❌ আপনি এখনো সমস্ত বাধ্যতামূলক চ্যানেল বা গ্রুপে জয়েন করেননি!", show_alert=True)

if __name__ == "__main__":
    keep_alive()
    # ব্যাকগ্রাউন্ডে রিয়েল-টাইম লাইভ এসএমএস মনিটর থ্রেড চালু
    Thread(target=background_live_sms_monitor, daemon=True).start()
    
    try: bot.delete_webhook(drop_pending_updates=True)
    except: pass
    print("🚀 Volt X SMS BOT সফলভাবে রান হচ্ছে...")
    bot.polling(none_stop=True)

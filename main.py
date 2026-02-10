import os
import time
import sqlite3
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from datetime import datetime

# --- CONFIGURATION (Safe Environment Variables) ---
API_TOKEN = os.getenv('BOT_TOKEN')
# Fetching the API link and Key from Railway Settings
INFO_API_URL = os.getenv('INFO_API_URL') 
API_SECRET_KEY = os.getenv('API_KEY') 

CHANNEL_ID = "@LighZYagami" 
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

last_search_time = {}

# --- DATABASE SETUP ---
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, 
                   searches_left INTEGER, 
                   total_refers INTEGER,
                   last_reset_date TEXT)''')
conn.commit()

# --- HELPER FUNCTIONS ---

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def get_user_data(user_id):
    cursor.execute("SELECT searches_left, total_refers, last_reset_date FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

def update_daily_limit(user_id, data):
    today = datetime.now().strftime('%Y-%m-%d')
    searches, refers, last_date = data
    if last_date != today:
        cursor.execute("UPDATE users SET searches_left = 10, last_reset_date = ? WHERE user_id = ?", (today, user_id))
        conn.commit()
        return (10, refers, today)
    return data

# --- COMMANDS ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args()
    today = datetime.now().strftime('%Y-%m-%d')
    
    data = get_user_data(user_id)
    if not data:
        referrer = args if (args.isdigit() and int(args) != user_id) else None
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, 10, 0, today))
        if referrer:
            cursor.execute("UPDATE users SET searches_left = searches_left + 1, total_refers = total_refers + 1 WHERE user_id = ?", (referrer,))
            try:
                await bot.send_message(referrer, "🎊 *New Referral Alert!*\nSomeone joined via your link. You got **+1 search credit**!")
            except:
                pass
        conn.commit()

    welcome_text = (
        f"👋 *Welcome to OSINT Lookup Bot!*\n\n"
        f"📢 *Requirement:* Join {CHANNEL_ID} to use this bot.\n"
        f"💰 *Daily Credits:* 10 Searches.\n"
        f"🤝 *Referral:* Get +1 credit per invite."
    )
    await message.reply(welcome_text, parse_mode="Markdown")

@dp.message_handler(commands=['profile'])
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    data = get_user_data(user_id)
    if not data: return await message.reply("Please /start the bot.")
    
    searches, refers, last_date = update_daily_limit(user_id, data)
    profile_msg = (
        f"👤 *YOUR PROFILE*\n"
        f"━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{user_id}`\n"
        f"🔍 Remaining Credits: **{searches}**\n"
        f"👥 Total Refers: **{refers}**"
    )
    await message.reply(profile_msg, parse_mode="Markdown")

@dp.message_handler(commands=['referral'])
async def cmd_referral(message: types.Message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await message.reply(f"🔗 *YOUR REFERRAL LINK*\n\n`{ref_link}`\n\nInvite friends for +1 credit per join!", parse_mode="Markdown")

@dp.message_handler(commands=['num'])
async def cmd_num(message: types.Message):
    user_id = message.from_user.id
    
    # Force Join Check
    if not await is_subscribed(user_id):
        return await message.reply(f"⚠️ *Access Denied!*\nPlease join {CHANNEL_ID} to use this bot.")

    data = get_user_data(user_id)
    if not data: return await message.reply("Please /start first.")
    
    searches, refers, last_date = update_daily_limit(user_id, data)
    if searches <= 0:
        return await message.reply("❌ *Limit Reached!*\nInvite friends or wait for tomorrow.")

    # Flood Protection
    current_time = time.time()
    if user_id in last_search_time and current_time - last_search_time[user_id] < 30:
        return await message.reply(f"⏳ Please wait {int(30-(current_time-last_search_time[user_id]))}s.")

    phone = message.get_args()
    if not phone: return await message.reply("❓ Usage: `/num 91888xxxxxx`", parse_mode="Markdown")

    # --- THE SECURE API CALL ---
    try:
        final_url = f"{INFO_API_URL}?key={API_SECRET_KEY}&num={phone}"
        response = requests.get(final_url, timeout=10)
        
        if response.status_code == 200:
            cursor.execute("UPDATE users SET searches_left = searches_left - 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            last_search_time[user_id] = current_time
            await message.reply(f"✅ *Lookup Results:* \n\n`{response.text}`", parse_mode="Markdown")
        else:
            await message.reply("❌ API is currently offline.")
    except Exception:
        await message.reply(f"⚠️ Connection error with API.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
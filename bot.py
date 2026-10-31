import os
import sys
import sqlite3
import time
import threading
import requests
import telebot
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Config & Keys ---
BOT_TOKEN = "9097713241:AAFjxbWR26Dj_YZwOCmwCz5_kVO2hjJ0vRE"
TG_SHARK_API_KEY = "tgsharkapi-WO-KNCM9K2unyWXcn6_Y6FgzbyLE3O"
BASE_URL = "https://tgsharkapi.store/api/v1"

ADMIN_ID = 8539777823
ADMIN_USERNAME = "@ub2_q"
UPI_ID = "noname0011@axl"
REFERRAL_COMMISSION_PERCENT = 5.0

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# --- Dummy HTTP Server for Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"HTTP Server listening on port {port}...", flush=True)
    server.serve_forever()

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            referrer_id INTEGER DEFAULT NULL,
            total_referrals INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id, referrer_id=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, referrer_id, total_referrals FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance, referrer_id, total_referrals) VALUES (?, 0.0, ?, 0)", (user_id, referrer_id))
        if referrer_id:
            cursor.execute("UPDATE users SET total_referrals = total_referrals + 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        balance = 0.0
    else:
        balance = row[0]
    conn.close()
    return balance

# --- Bot Handlers ---
@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        args = message.text.split()
        referrer_id = None
        if len(args) > 1 and args[1].startswith("ref_"):
            try:
                potential_ref = int(args[1].replace("ref_", ""))
                if potential_ref != message.chat.id:
                    referrer_id = potential_ref
            except:
                pass

        get_user(message.chat.id, referrer_id)

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Wallet Balance", callback_data="wallet"),
            InlineKeyboardButton("Add Fund (UPI)", callback_data="add_fund"),
            InlineKeyboardButton("Refer & Earn (5%)", callback_data="refer")
        )
        bot.send_message(
            message.chat.id,
            "👋 Welcome! Number buy karne aur balance manage karne ke liye options choose karein:",
            reply_markup=markup
        )
    except Exception as e:
        print(f"Error in start: {e}", flush=True)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        user_id = call.message.chat.id

        if call.data == "wallet":
            bal = get_user(user_id)
            bot.answer_callback_query(call.id)
            bot.send_message(user_id, f"💰 Aapka Wallet Balance: Rs {bal:.2f}")

        elif call.data == "add_fund":
            bot.answer_callback_query(call.id)
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("Rs 20", callback_data="pay_20"),
                InlineKeyboardButton("Rs 50", callback_data="pay_50"),
                InlineKeyboardButton("Rs 100", callback_data="pay_100"),
                InlineKeyboardButton("Rs 200", callback_data="pay_200")
            )
            bot.send_message(user_id, "Amount choose karein:", reply_markup=markup)

        elif call.data.startswith("pay_"):
            amount = call.data.split("_")[1]
            bot.answer_callback_query(call.id)
            bot.send_message(
                user_id,
                f"Deposit Amount: Rs {amount}.00\n"
                f"Pay on UPI: {UPI_ID}\n"
                f"Payment ke baad screenshot ya 12-digit UTR send karein!\n"
                f"Support: {ADMIN_USERNAME}"
            )

        elif call.data == "refer":
            bot.answer_callback_query(call.id)
            conn = sqlite3.connect("bot_database.db")
            cursor = conn.cursor()
            cursor.execute("SELECT total_referrals FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            total_refs = row[0] if row else 0
            conn.close()

            bot_info = bot.get_me()
            ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
            bot.send_message(
                user_id,
                f"Refer & Earn ({REFERRAL_COMMISSION_PERCENT}%)\n\n"
                f"Link: {ref_link}\n"
                f"Total Referrals: {total_refs}"
            )
    except Exception as e:
        print(f"Callback error: {e}", flush=True)

@bot.message_handler(content_types=['photo', 'text'])
def payment_proof_handler(message):
    try:
        if message.text and message.text.startswith('/'):
            return

        bot.send_message(
            message.chat.id,
            f"Proof received! 10 minutes ka wait karein, check karke add kar diya jayega.\nSupport: {ADMIN_USERNAME}"
        )
        if message.photo:
            bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        elif message.text:
            bot.send_message(ADMIN_ID, f"UTR/Message from user {message.chat.id}:\n{message.text}")
    except Exception as e:
        print(f"Proof handler error: {e}", flush=True)

# --- Start Server & Polling ---
if __name__ == '__main__':
    # Web server thread
    server_thread = threading.Thread(target=run_http_server, daemon=True)
    server_thread.start()

    print("Clearing old webhooks & pending updates...", flush=True)
    try:
        bot.remove_webhook()
    except Exception:
        pass

    print("Bot polling started successfully!", flush=True)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20, skip_pending=True)
        except Exception as e:
            print(f"Polling loop restart after error: {e}", flush=True)
            time.sleep(2)

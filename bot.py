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
BOT_TOKEN = "9097713241:AAGxalKh5kYd-mdm3TU4OML9-TCHQduEw_Q"
TG_SHARK_API_KEY = "tgsharkapi-WO-KNCM9K2unyWXcn6_Y6FgzbyLE3O"
BASE_URL = "https://tgsharkapi.store/api/v1"

ADMIN_ID = 8539777823
ADMIN_USERNAME = "@ub2_q"
UPI_ID = "noname0011@axl"
REFERRAL_COMMISSION_PERCENT = 5.0

# Tera profit per account (₹20 added)
PROFIT_MARGIN = 20.0

# Base API Price + Tera ₹20 Profit = Selling Price
COUNTRIES = {
    "india": {"name": "🇮🇳 India", "price": 35.0 + PROFIT_MARGIN},          # ₹55
    "russia": {"name": "🇷🇺 Russia", "price": 40.0 + PROFIT_MARGIN},        # ₹60
    "usa": {"name": "🇺🇸 USA", "price": 45.0 + PROFIT_MARGIN},              # ₹65
    "indonesia": {"name": "🇮🇩 Indonesia", "price": 30.0 + PROFIT_MARGIN},  # ₹50
    "vietnam": {"name": "🇻🇳 Vietnam", "price": 32.0 + PROFIT_MARGIN},      # ₹52
    "philippines": {"name": "🇵🇭 Philippines", "price": 38.0 + PROFIT_MARGIN}# ₹58
}

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

def deduct_balance(user_id, amount):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# --- TG Shark API Functions ---
def order_number(country):
    try:
        url = f"{BASE_URL}/order"
        params = {"api_key": TG_SHARK_API_KEY, "country": country, "service": "tg"}
        res = requests.get(url, params=params, timeout=15).json()
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_sms(order_id):
    try:
        url = f"{BASE_URL}/get_sms"
        params = {"api_key": TG_SHARK_API_KEY, "order_id": order_id}
        res = requests.get(url, params=params, timeout=15).json()
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}

def cancel_order(order_id):
    try:
        url = f"{BASE_URL}/cancel"
        params = {"api_key": TG_SHARK_API_KEY, "order_id": order_id}
        res = requests.get(url, params=params, timeout=15).json()
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
            InlineKeyboardButton("📱 Buy Number", callback_data="buy_num"),
            InlineKeyboardButton("💰 Wallet Balance", callback_data="wallet"),
            InlineKeyboardButton("➕ Add Fund (UPI)", callback_data="add_fund"),
            InlineKeyboardButton("🎁 Refer & Earn (5%)", callback_data="refer")
        )
        bot.send_message(
            message.chat.id,
            "👋 Welcome to Kissu Num Bot!\n\nOTP & Virtual Numbers buy karne ke liye niche diye option choose karein:",
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

        elif call.data == "buy_num":
            bot.answer_callback_query(call.id)
            markup = InlineKeyboardMarkup(row_width=2)
            buttons = []
            for c_key, c_val in COUNTRIES.items():
                buttons.append(InlineKeyboardButton(f"{c_val['name']} (₹{int(c_val['price'])})", callback_data=f"buy_{c_key}"))
            markup.add(*buttons)
            markup.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="back_home"))
            bot.send_message(user_id, "📍 Select Country for Telegram Number:", reply_markup=markup)

        elif call.data.startswith("buy_"):
            c_key = call.data.replace("buy_", "")
            if c_key in COUNTRIES:
                bot.answer_callback_query(call.id)
                price = COUNTRIES[c_key]["price"]
                bal = get_user(user_id)
                
                if bal < price:
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("➕ Add Fund Now", callback_data="add_fund"))
                    bot.send_message(user_id, f"❌ Insufficient Balance!\nPrice: ₹{int(price)}\nAapka Balance: ₹{bal:.2f}\n\nPehle fund add karein.", reply_markup=markup)
                    return

                wait_msg = bot.send_message(user_id, f"⏳ {COUNTRIES[c_key]['name']} number book ho raha hai, please wait...")
                
                res = order_number(c_key)
                if res.get("status") in ["success", 200, True] and "number" in res:
                    number = res.get("number")
                    order_id = res.get("order_id", res.get("id"))
                    deduct_balance(user_id, price)
                    
                    # Admin ko profit alert notify karega
                    try:
                        bot.send_message(ADMIN_ID, f"🤑 Naya Order Success!\nUser: `{user_id}`\nCountry: {COUNTRIES[c_key]['name']}\nSelling Price: ₹{price}\nTera Profit: ₹{PROFIT_MARGIN}")
                    except Exception:
                        pass

                    otp_markup = InlineKeyboardMarkup(row_width=2)
                    otp_markup.add(
                        InlineKeyboardButton("📩 Get OTP", callback_data=f"otp_{order_id}"),
                        InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"cancel_{order_id}_{c_key}")
                    )
                    bot.edit_message_text(
                        f"✅ Number Booked!\n\n📞 Number: `{number}`\n🆔 Order ID: `{order_id}`\n💰 Charged: ₹{int(price)}\n\nTelegram app me number dalein aur **Get OTP** par click karein.",
                        chat_id=user_id,
                        message_id=wait_msg.message_id,
                        parse_mode="Markdown",
                        reply_markup=otp_markup
                    )
                else:
                    err_text = res.get("message", "Stock available nahi hai ya API issue")
                    bot.edit_message_text(f"❌ Number order failed: {err_text}\nThodi der baad try karein.", chat_id=user_id, message_id=wait_msg.message_id)

        elif call.data.startswith("otp_"):
            order_id = call.data.replace("otp_", "")
            bot.answer_callback_query(call.id, text="Checking SMS...")
            res = check_sms(order_id)
            sms_code = res.get("sms") or res.get("code") or res.get("otp")
            
            if sms_code:
                bot.send_message(user_id, f"🎉 **Aapka Telegram OTP hai:** `{sms_code}`", parse_mode="Markdown")
            else:
                bot.send_message(user_id, f"⏳ OTP abhi tak nahi aaya hai. Wait karke dobara **Get OTP** click karein (Order ID: {order_id}).")

        elif call.data.startswith("cancel_"):
            parts = call.data.split("_")
            order_id = parts[1]
            c_key = parts[2]
            refund_amount = COUNTRIES.get(c_key, {}).get("price", 0.0)
            
            cancel_order(order_id)
            conn = sqlite3.connect("bot_database.db")
            c = conn.cursor()
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (refund_amount, user_id))
            conn.commit()
            conn.close()
            
            bot.answer_callback_query(call.id, text="Order Cancelled!")
            bot.send_message(user_id, f"✅ Order `{order_id}` cancel ho gaya. ₹{int(refund_amount)} aapke wallet me refund ho gaye.", parse_mode="Markdown")

        elif call.data == "back_home":
            bot.answer_callback_query(call.id)
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("📱 Buy Number", callback_data="buy_num"),
                InlineKeyboardButton("💰 Wallet Balance", callback_data="wallet"),
                InlineKeyboardButton("➕ Add Fund (UPI)", callback_data="add_fund"),
                InlineKeyboardButton("🎁 Refer & Earn (5%)", callback_data="refer")
            )
            bot.send_message(user_id, "Main Menu:", reply_markup=markup)

        elif call.data == "add_fund":
            bot.answer_callback_query(call.id)
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("Rs 50", callback_data="pay_50"),
                InlineKeyboardButton("Rs 100", callback_data="pay_100"),
                InlineKeyboardButton("Rs 200", callback_data="pay_200"),
                InlineKeyboardButton("Rs 500", callback_data="pay_500")
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


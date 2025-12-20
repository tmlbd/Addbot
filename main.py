import os
import threading
import time
import requests
import telebot
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson.objectid import ObjectId

# --- CONFIGURATION (Environment Variables) ---
MONGO_URI = os.environ.get("MONGO_URI")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASS", "admin123")
APP_URL_ENV = os.environ.get("APP_URL", "").rstrip('/') # ব্লগারের পোস্ট লিঙ্ক
SECRET_KEY = os.environ.get("SECRET_KEY", "EARN_PRO_API_MASTER_2025")

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app) # এটি ব্লগার থেকে রিকোয়েস্ট আসার অনুমতি দিবে

# Bot Setup
bot = None
BOT_USERNAME = "Bot"
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        me = bot.get_me()
        BOT_USERNAME = me.username
    except: pass

# Database Connection
client = MongoClient(MONGO_URI)
db = client['mega_earning_blogger_v1']
users_collection = db['users']
settings_collection = db['settings']
withdraws_collection = db['withdrawals']

def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config", "ad_count_per_click": 2, "ad_interval": 3, "ad_rate": 0.50,
            "ref_commission": 2.00, "min_withdraw": 50.00, "min_recharge": 20.00,
            "recharge_on": True, "daily_ad_limit": 50, "reset_hours": 24,
            "withdraw_methods": ["Bkash", "Nagad", "Rocket"],
            "recharge_methods": ["GP", "Robi", "Airtel"],
            "notice": "স্বাগতম! কাজ শুরু করুন সঠিক VPN দিয়ে।",
            "zone_id": "10351894", "vpn_on": False, "allowed_countries": "US,GB,CA"
        }
        settings_collection.insert_one(default)
        return default
    return setts

# --- TELEGRAM BOT LOGIC ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        
        user = users_collection.find_one({"user_id": uid})
        balance = user['balance'] if user else 0.0
        
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        # ব্লগার ইউআরএল ভেরিয়েবল থেকে নেওয়া
        if not APP_URL_ENV:
            bot.reply_to(message, "❌ Admin: Please set APP_URL (Blogger Link) in Render Variables.")
            return

        dashboard_url = f"{APP_URL_ENV}/?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        msg = (f"👋 **স্বাগতম, {name}!**\n\n💰 ব্যালেন্স: `{balance:.2f}` ৳\n📢 নোটিশ: {config['notice']}\n\n👇 কাজ শুরু করতে নিচের বাটনে ক্লিক করুন।")
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

# --- API FOR BLOGGER ---

@app.route('/api/config', methods=['GET'])
def api_config():
    config = get_settings()
    config.pop('_id', None)
    return jsonify(config)

@app.route('/api/user', methods=['POST'])
def api_user():
    data = request.json
    uid, name, ref_by = str(data.get('id')), data.get('name'), data.get('ref')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    config = get_settings()
    now = datetime.now()

    user = users_collection.find_one({"user_id": uid})
    if not user:
        if users_collection.find_one({"ip_address": ip}):
            return jsonify({"success": False, "message": "Multiple accounts blocked!"})
        
        user_data = {"user_id": uid, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, 
                     "referred_by": ref_by, "daily_views": 0, "last_reset_time": now}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != uid:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data

    # Auto Reset
    reset_delta = timedelta(hours=config.get('reset_hours', 24))
    if now >= user.get('last_reset_time', now) + reset_delta:
        users_collection.update_one({"user_id": uid}, {"$set": {"daily_views": 0, "last_reset_time": now}})
        user['daily_views'] = 0

    user.pop('_id', None)
    return jsonify({"success": True, "user": user, "bot_username": BOT_USERNAME})

@app.route('/api/update_balance', methods=['POST'])
def update_balance():
    uid = request.json.get('user_id')
    config = get_settings()
    user = users_collection.find_one({"user_id": uid})
    if user['daily_views'] >= config['daily_ad_limit']: return jsonify({"success": False, "message": "Limit Reached!"})
    users_collection.update_one({"user_id": uid}, {"$inc": {"balance": config['ad_rate'], "daily_views": 1}})
    u = users_collection.find_one({"user_id": uid})
    return jsonify({"success": True, "new_balance": u['balance']})

@app.route('/api/request_payment', methods=['POST'])
def request_payment():
    data = request.json
    config = get_settings()
    user = users_collection.find_one({"user_id": data['user_id']})
    min_amt = config['min_recharge'] if data['type'] == 'Recharge' else config['min_withdraw']
    if data['amount'] < min_amt or user['balance'] < data['amount']:
        return jsonify({"success": False, "message": "Check balance/limit!"})
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "method": data['method'], "type": data['type'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Request submitted!"})

# --- PREMIUM ADMIN PANEL ---

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if request.form.get('pass') == ADMIN_PASSWORD_ENV:
            session['logged'] = True
            return redirect(url_for('admin'))
    if not session.get('logged'): return '<body style="background:#0b0f1a;color:white;text-align:center;padding:100px;"><h2>Admin Login</h2><form method="POST"><input name="pass" type="password" style="padding:10px;"><button type="submit">Login</button></form></body>'
    
    users = list(users_collection.find().limit(50))
    withdraws = list(withdraws_collection.find({"status": "Pending"}))
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Master Admin</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: sans-serif; background: #0b0f1a; color: white; padding: 20px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
            .card { background: #161e31; padding: 20px; border-radius: 15px; border: 1px solid #334155; }
            input, textarea, select { width: 100%; padding: 10px; margin: 8px 0; border-radius: 5px; background: #0b0f1a; color: white; border: 1px solid #334155; box-sizing: border-box; }
            button { background: #10b981; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1 style="text-align:center; color:#6366f1;">💎 Master Admin</h1>
        <div class="grid">
            <div class="card">
                <h3>⚙️ Settings</h3>
                <form method="POST" action="/admin/save_settings">
                    Notice: <textarea name="notice">{{config.notice}}</textarea>
                    Ad Rate: <input name="ad_rate" step="0.01" value="{{config.ad_rate}}">
                    Ads Per Click: <input name="ad_count_per_click" type="number" value="{{config.ad_count_per_click}}">
                    Ad Interval (Sec): <input name="ad_interval" type="number" value="{{config.ad_interval}}">
                    Zone ID: <input name="zone_id" value="{{config.zone_id}}">
                    Min Withdraw: <input name="min_withdraw" value="{{config.min_withdraw}}">
                    Min Recharge: <input name="min_recharge" value="{{config.min_recharge}}">
                    Withdraw Methods: <input name="withdraw_methods" value="{{ config.withdraw_methods|join(', ') }}">
                    Recharge Methods: <input name="recharge_methods" value="{{ config.recharge_methods|join(', ') }}">
                    <button type="submit">Update Everything</button>
                </form>
            </div>
            <div class="card">
                <h3>💰 Requests</h3>
                {% for w in withdraws %}
                <p>{{w.name}} - {{w.type}} - ৳{{w.amount}} <a href="/admin/pay/{{w._id}}" style="color:red;">Paid</a></p>
                {% endfor %}
            </div>
        </div>
        <div class="card" style="margin-top:20px;">
            <h3>👥 User Control</h3>
            {% for u in users %}
            <form action="/admin/edit_user/{{u.user_id}}" method="POST" style="display:flex;gap:5px;margin-bottom:5px;">
                <span>{{u.name}}</span>
                <input name="balance" value="{{u.balance}}" style="width:70px;">
                <button type="submit" style="width:auto;padding:5px;">Save</button>
            </form>
            {% endfor %}
        </div>
        <br><center><a href="/logout" style="color:grey;">Logout</a></center>
    </body>
    </html>
    """, config=config, users=users, withdraws=withdraws)

@app.route('/admin/save_settings', methods=['POST'])
def save_settings():
    if session.get('logged'):
        try:
            settings_collection.update_one({"id": "config"}, {"$set": {
                "notice": request.form.get('notice'), "ad_rate": float(request.form.get('ad_rate')),
                "ad_count_per_click": int(request.form.get('ad_count_per_click')), "ad_interval": int(request.form.get('ad_interval')),
                "min_withdraw": float(request.form.get('min_withdraw')), "min_recharge": float(request.form.get('min_recharge')),
                "withdraw_methods": [m.strip() for m in request.form.get('withdraw_methods').split(',')],
                "recharge_methods": [r.strip() for r in request.form.get('recharge_methods').split(',')],
                "zone_id": request.form.get('zone_id')
            }}, upsert=True)
        except: pass
    return redirect(url_for('admin'))

@app.route('/admin/edit_user/<uid>', methods=['POST'])
def edit_user(uid):
    if session.get('logged'):
        users_collection.update_one({"user_id": uid}, {"$set": {"balance": float(request.form.get('balance', 0))}})
    return redirect(url_for('admin'))

@app.route('/admin/pay/<wid>')
def pay_withdraw(wid):
    if session.get('logged'): withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

@app.route('/logout')
def logout(): session.pop('logged', None); return redirect(url_for('admin'))

if __name__ == "__main__":
    if bot:
        bot.remove_webhook()
        threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

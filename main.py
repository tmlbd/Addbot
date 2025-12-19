import os
import threading
import time
import requests
import telebot
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

# --- CONFIGURATION (Environment Variables) ---
MONGO_URI = os.environ.get("MONGO_URI")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# রেন্ডারে এই নতুন ভেরিয়েবলটি যোগ করবেন (যেমন: https://your-app.onrender.com)
APP_URL_ENV = os.environ.get("APP_URL", "").rstrip('/') 
ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASS", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "PREMIUM_ULTIMATE_FIX_2025")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Bot Setup
bot = None
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        BOT_USERNAME = bot.get_me().username
    except:
        BOT_USERNAME = "Bot"

# Database Connection
client = MongoClient(MONGO_URI)
db = client['mega_earning_v12']
users_collection = db['users']
settings_collection = db['settings']
withdraws_collection = db['withdrawals']

def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config", "ad_count": 1, "ad_rate": 0.50, "ref_commission": 2.00,
            "min_withdraw": 10.00, "max_withdraw": 1000.00, "withdraw_methods": "Bkash, Nagad",
            "notice": "সঠিক VPN কানেক্ট করে কাজ করুন!", "zone_id": "10341337", 
            "vpn_on": False, "allowed_countries": "US,GB,CA", "app_url": APP_URL_ENV
        }
        settings_collection.insert_one(default)
        return default
    return setts

# --- TELEGRAM BOT ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        # সচল ইউআরএল খুঁজে বের করা
        final_url = APP_URL_ENV if APP_URL_ENV else config.get('app_url')
        
        if not final_url:
            bot.reply_to(message, "❌ অ্যাডমিন এখনো ওয়েবসাইট লিঙ্ক সেটআপ করেনি। রেন্ডারে APP_URL ভেরিয়েবল যোগ করুন।")
            return

        dashboard_url = f"{final_url}/?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, f"👋 স্বাগতম {name}!\n💰 এড দেখে আয় শুরু করতে নিচের বাটনে ক্লিক করুন।", reply_markup=markup)

# --- USER DASHBOARD ---
USER_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: white; margin: 0; text-align: center; }
        .notice { background: #f59e0b; color: black; padding: 10px; font-weight: bold; }
        .container { padding: 20px; max-width: 450px; margin: auto; }
        .card { background: #1e293b; border-radius: 20px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .balance-box { background: linear-gradient(135deg, #10b981, #059669); padding: 20px; border-radius: 15px; margin: 15px 0; }
        .btn { width: 100%; padding: 15px; border: none; border-radius: 10px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 10px; color: white; }
    </style>
</head>
<body>
    <div class="notice">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=3b82f6&color=fff" style="width:70px; border-radius:50%;">
            <h3>{{ user.name }}</h3>
            <div class="balance-box">
                <small>Available Balance</small>
                <div style="font-size: 34px; font-weight: bold;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            <button class="btn" style="background:#3b82f6;" onclick="startWork()">WATCH ADS</button>
            <button class="btn" style="background:#f59e0b;" onclick="openW()">WITHDRAW</button>
            <div style="text-align: left; font-size: 12px; margin-top: 15px; color: #94a3b8;">
                ID: {{ user.user_id }} | Refers: {{ user.ref_count }}<br>
                Ref Link: t.me/{{ bot_username }}?start={{ user.user_id }}
            </div>
        </div>
    </div>
    <script>
    function startWork() {
        let zid = "{{ config.zone_id }}";
        if(typeof window['show_'+zid] === 'function') {
            for(let i=0; i< {{config.ad_count}}; i++){ window['show_'+zid](); }
            fetch('/update_balance', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:"{{user.user_id}}"})})
            .then(res=>res.json()).then(data=> { if(data.success) document.getElementById('bal').innerText = data.new_balance.toFixed(2); });
        }
    }
    function openW() {
        let amt = prompt("Amount:"); let acc = prompt("Number:");
        if(amt && acc) {
            fetch('/request_withdraw', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:"{{user.user_id}}", amount:parseFloat(amt), account:acc})})
            .then(res=>res.json()).then(data=>alert(data.message));
        }
    }
    </script>
</body>
</html>
"""

# --- VIBRANT ADMIN PANEL ---
ADMIN_PANEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: white; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; }
        input, textarea, select { width: 100%; padding: 10px; margin: 8px 0; border-radius: 5px; background: #0f172a; color: white; border: 1px solid #334155; }
        button { background: #10b981; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 10px; border-bottom: 1px solid #334155; text-align: left; font-size: 13px; }
    </style>
</head>
<body>
    <h1 style="text-align:center; color:#818cf8;">💎 Master Admin Dashboard</h1>
    
    <div class="grid">
        <div class="card">
            <h3>⚙️ App Settings</h3>
            <form method="post">
                Notice: <textarea name="notice">{{config.notice}}</textarea>
                Ad Rate: <input name="ad_rate" step="0.01" value="{{config.ad_rate}}">
                Ad Count: <input name="ad_count" type="number" value="{{config.ad_count}}">
                Min Withdraw: <input name="min_withdraw" value="{{config.min_withdraw}}">
                Zone ID: <input name="zone_id" value="{{config.zone_id}}">
                VPN (on/off): <select name="vpn_on">
                    <option value="on" {% if config.vpn_on %}selected{% endif %}>ON</option>
                    <option value="off" {% if not config.vpn_on %}selected{% endif %}>OFF</option>
                </select>
                <button type="submit">Update Settings</button>
            </form>
        </div>

        <div class="card">
            <h3>💰 Withdraw Requests</h3>
            <table>
                {% for w in withdraws %}
                <tr>
                    <td>{{w.name}}<br><small>{{w.account}}</small></td>
                    <td>৳{{w.amount}}</td>
                    <td><a href="/admin/pay/{{w._id}}" style="color:#ef4444;">Paid</a></td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>

    <div class="card" style="margin-top:20px;">
        <h3>👥 User Management</h3>
        <table>
            <tr><th>Name</th><th>Balance</th><th>Action</th></tr>
            {% for u in users %}
            <tr>
                <form action="/admin/edit_user/{{u.user_id}}" method="post">
                    <td>{{u.name}}<br><small>{{u.user_id}}</small></td>
                    <td><input name="balance" value="{{u.balance}}" style="width:70px; margin:0;"></td>
                    <td><button type="submit" style="width:auto; padding:5px 10px;">Save</button></td>
                </form>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def home():
    user_id = request.args.get('id')
    name = request.args.get('name', 'User')
    ref_by = request.args.get('ref')
    
    if not user_id:
        return "<h1>Join via Bot first!</h1>", 403
    
    config = get_settings()
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
        ip_exists = users_collection.find_one({"ip_address": ip})
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, "referred_by": ref_by, "created_at": datetime.now()}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != user_id and not ip_exists:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data
    
    return render_template_string(USER_DASHBOARD, user=user, config=config, bot_username=BOT_USERNAME)

@app.route('/update_balance', methods=['POST'])
def update_balance():
    uid = request.json.get('user_id')
    config = get_settings()
    users_collection.update_one({"user_id": uid}, {"$inc": {"balance": config['ad_rate']}})
    u = users_collection.find_one({"user_id": uid})
    return jsonify({"success": True, "new_balance": u['balance']})

@app.route('/request_withdraw', methods=['POST'])
def request_withdraw():
    data = request.json
    config = get_settings()
    user = users_collection.find_one({"user_id": data['user_id']})
    if data['amount'] < config['min_withdraw'] or user['balance'] < data['amount']:
        return jsonify({"success": False, "message": "Invalid Balance!"})
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Withdraw Requested!"})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if session.get('logged'):
            try:
                settings_collection.update_one({"id": "config"}, {"$set": {
                    "notice": request.form.get('notice'),
                    "ad_rate": float(request.form.get('ad_rate', 0.50)),
                    "ad_count": int(request.form.get('ad_count', 1)),
                    "min_withdraw": float(request.form.get('min_withdraw', 10.00)),
                    "zone_id": request.form.get('zone_id'),
                    "vpn_on": True if request.form.get('vpn_on') == 'on' else False
                }})
                return redirect(url_for('admin'))
            except: return "Invalid input. Use numbers for rates/limits."
        elif request.form.get('pass') == ADMIN_PASSWORD_ENV:
            session['logged'] = True
            return redirect(url_for('admin'))
    
    if not session.get('logged'):
        return '<body style="background:#0f172a;color:white;text-align:center;padding:100px;"><form method="post"><h2>Admin Login</h2><input name="pass" type="password"><br><br><button type="submit">Login</button></form></body>'
    
    users = list(users_collection.find().limit(50))
    withdraws = list(withdraws_collection.find({"status": "Pending"}))
    return render_template_string(ADMIN_PANEL, config=config, users=users, withdraws=withdraws)

@app.route('/admin/edit_user/<uid>', methods=['POST'])
def edit_user(uid):
    if session.get('logged'):
        users_collection.update_one({"user_id": uid}, {"$set": {"balance": float(request.form.get('balance', 0))}})
    return redirect(url_for('admin'))

@app.route('/admin/pay/<wid>')
def pay_withdraw(wid):
    if session.get('logged'):
        withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

if __name__ == "__main__":
    if bot:
        bot.remove_webhook()
        threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

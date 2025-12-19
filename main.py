import os
import threading
import time
import requests
import telebot
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson.objectid import ObjectId

# --- CONFIGURATION (Environment Variables) ---
MONGO_URI = os.environ.get("MONGO_URI")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASS", "admin123")
APP_URL_ENV = os.environ.get("APP_URL", "").rstrip('/')
SECRET_KEY = os.environ.get("SECRET_KEY", "PREMIUM_RECHARGE_SYSTEM_2025")

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
db = client['mega_earning_v21']
users_collection = db['users']
settings_collection = db['settings']
withdraws_collection = db['withdrawals']

def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config",
            "ad_count_per_click": 1,
            "ad_rate": 0.50,
            "ref_commission": 2.00,
            "min_withdraw": 10.00,
            "max_withdraw": 1000.00,
            "min_recharge": 20.00, # মোবাইল রিচার্জের সর্বনিম্ন সীমা
            "recharge_on": True,   # রিচার্জ সিস্টেম অন/অফ
            "daily_ad_limit": 50,
            "reset_hours": 24,
            "reset_minutes": 0,
            "withdraw_methods": ["Bkash", "Nagad", "Rocket"],
            "notice": "সঠিক VPN কানেক্ট করে কাজ করুন!",
            "zone_id": "10341337",
            "vpn_on": False,
            "allowed_countries": "US,GB,CA",
            "app_url": APP_URL_ENV
        }
        settings_collection.insert_one(default)
        return default
    return setts

def get_user_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

# --- TELEGRAM BOT LOGIC ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        final_url = APP_URL_ENV if APP_URL_ENV else config.get('app_url')
        dashboard_url = f"{final_url}/?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, f"👋 স্বাগতম {name}!\n💰 এড দেখে আয় শুরু করতে নিচের বাটনে ক্লিক করুন।", reply_markup=markup)

# --- USER DASHBOARD (PREMIUM UI WITH RECHARGE) ---
USER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn Pro | Dashboard</title>
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0f172a; --card: #1e293b; --primary: #3b82f6; --success: #10b981; --accent: #f59e0b; --recharge: #8b5cf6; }
        body { font-family: 'Poppins', sans-serif; background: var(--bg); color: white; margin: 0; text-align: center; }
        .notice { background: var(--accent); color: black; padding: 12px; font-weight: 600; font-size: 13px; }
        .container { width: 100%; max-width: 480px; padding: 20px; margin: auto; box-sizing: border-box; }
        .card { background: var(--card); border-radius: 24px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .balance-card { background: linear-gradient(135deg, var(--success), #059669); border-radius: 20px; padding: 20px; margin: 20px 0; }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .stat-item { background: #334155; padding: 12px; border-radius: 16px; font-size: 12px; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 16px; font-size: 16px; font-weight: 600; cursor: pointer; margin-bottom: 12px; color: white; transition: 0.2s; }
        .btn-work { background: var(--primary); box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4); }
        .btn-withdraw { background: #475569; }
        .btn-recharge { background: var(--recharge); box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4); }
        
        .modal { display: none; position: fixed; z-index: 10; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); }
        .modal-content { background: var(--card); margin: 15% auto; padding: 25px; width: 85%; max-width: 400px; border-radius: 20px; text-align: left; }
        input, select { width: 100%; padding: 12px; margin: 10px 0; border-radius: 10px; border: 1px solid #334155; background: #0f172a; color: white; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="notice">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=random&color=fff" style="width:70px; border-radius:50%; margin-bottom:10px;">
            <h2 style="margin:0;">{{ user.name }}</h2>
            <div class="balance-card">
                <small>Current Balance</small>
                <span style="font-size: 34px; font-weight: 700; display: block;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></span>
            </div>
            <div class="stats-grid">
                <div class="stat-item"><b>{{ user.ref_count }}</b><br>Refers</div>
                <div class="stat-item"><b id="daily_left">{{ config.daily_ad_limit - user.daily_views }}</b><br>Ads Left</div>
            </div>
            <button class="btn btn-work" onclick="startWork()">WATCH ADS ({{ config.ad_count_per_click }})</button>
            <button class="btn btn-withdraw" onclick="document.getElementById('withdrawModal').style.display='block'">WITHDRAWAL</button>
            
            {% if config.recharge_on %}
            <button class="btn btn-recharge" onclick="document.getElementById('rechargeModal').style.display='block'">MOBILE RECHARGE</button>
            {% endif %}

            <p style="font-size:10px; color:#94a3b8; margin-top:10px;">Next Reset In: <span id="timer">--:--:--</span></p>
        </div>
    </div>

    <!-- Withdraw Modal -->
    <div id="withdrawModal" class="modal">
        <div class="modal-content">
            <h3 style="margin:0;">Withdrawal</h3>
            <select id="w_method">{% for m in config.withdraw_methods %}<option value="{{m}}">{{m}}</option>{% endfor %}</select>
            <input type="number" id="w_amount" placeholder="Amount (Min ৳{{config.min_withdraw}})">
            <input type="text" id="w_account" placeholder="Wallet Number">
            <button class="btn btn-work" onclick="submitRequest('Withdraw', 'w_method', 'w_amount', 'w_account')">Confirm</button>
            <button class="btn" onclick="document.getElementById('withdrawModal').style.display='none'" style="background:transparent; margin:0;">Cancel</button>
        </div>
    </div>

    <!-- Recharge Modal -->
    <div id="rechargeModal" class="modal">
        <div class="modal-content">
            <h3 style="margin:0;">Mobile Recharge</h3>
            <select id="r_operator">
                <option value="Grameenphone">Grameenphone</option>
                <option value="Banglalink">Banglalink</option>
                <option value="Robi">Robi</option>
                <option value="Airtel">Airtel</option>
                <option value="Teletalk">Teletalk</option>
            </select>
            <input type="number" id="r_amount" placeholder="Amount (Min ৳{{config.min_recharge}})">
            <input type="text" id="r_number" placeholder="Mobile Number">
            <button class="btn btn-recharge" onclick="submitRequest('Recharge', 'r_operator', 'r_amount', 'r_number')">Confirm Recharge</button>
            <button class="btn" onclick="document.getElementById('rechargeModal').style.display='none'" style="background:transparent; margin:0;">Cancel</button>
        </div>
    </div>

    <script>
    function startWork() {
        let left = parseInt(document.getElementById('daily_left').innerText);
        if(left <= 0) return alert("লিমিট শেষ!");
        let zid = "{{ config.zone_id }}";
        if(typeof window['show_'+zid] === 'function') {
            for(let i=0; i< {{config.ad_count_per_click}}; i++){ 
                setTimeout(() => { window['show_'+zid](); }, i * 2500);
            }
            fetch('/update_balance', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:"{{user.user_id}}"})})
            .then(res=>res.json()).then(data=> {
                if(data.success) {
                    document.getElementById('bal').innerText = data.new_balance.toFixed(2);
                    document.getElementById('daily_left').innerText = data.daily_left;
                }
            });
        }
    }

    function submitRequest(type, methodId, amountId, accountId) {
        let method = document.getElementById(methodId).value;
        let amt = parseFloat(document.getElementById(amountId).value);
        let acc = document.getElementById(accountId).value;
        
        let min = (type === 'Recharge') ? {{config.min_recharge}} : {{config.min_withdraw}};
        if(amt < min) return alert("Minimum " + type + " is ৳" + min);
        if(!acc) return alert("Please enter number");

        fetch('/request_payment', {
            method:'POST', 
            headers:{'Content-Type':'application/json'}, 
            body:JSON.stringify({user_id:"{{user.user_id}}", amount:amt, account:acc, method:method, type:type})
        }).then(res=>res.json()).then(data=>{ alert(data.message); location.reload(); });
    }

    function updateTimer() {
        const nextReset = new Date("{{ next_reset }}").getTime();
        const diff = nextReset - new Date().getTime();
        if (diff <= 0) { location.reload(); return; }
        const h = Math.floor((diff % 86400000) / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        document.getElementById('timer').innerText = h + "h " + m + "m " + s + "s";
    }
    setInterval(updateTimer, 1000);
    </script>
</body>
</html>
"""

# --- VIBRANT ADMIN PANEL ---
ADMIN_PANEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Master Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: white; padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 20px; }
        input, select, textarea { width: 100%; padding: 10px; margin: 8px 0; border-radius: 8px; background: #0f172a; color: white; border: 1px solid #334155; box-sizing: border-box; }
        button { background: #10b981; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        th, td { padding: 10px; border-bottom: 1px solid #334155; text-align: left; }
    </style>
</head>
<body>
    <h1 style="text-align:center; color:#818cf8;">👑 Admin Control Panel</h1>
    <div class="grid">
        <div class="card">
            <h3>⚙️ App Settings</h3>
            <form method="post">
                Notice: <textarea name="notice">{{config.notice}}</textarea>
                Ad Rate: <input name="ad_rate" step="0.01" value="{{config.ad_rate}}">
                Daily Limit: <input name="daily_ad_limit" type="number" value="{{config.daily_ad_limit}}">
                Min Withdraw: <input name="min_withdraw" value="{{config.min_withdraw}}">
                Min Recharge: <input name="min_recharge" value="{{config.min_recharge}}">
                Recharge Status: <select name="recharge_on">
                    <option value="on" {% if config.recharge_on %}selected{% endif %}>ON</option>
                    <option value="off" {% if not config.recharge_on %}selected{% endif %}>OFF</option>
                </select>
                Withdraw Methods: <input name="withdraw_methods" value="{{ config.withdraw_methods|join(', ') }}">
                Zone ID: <input name="zone_id" value="{{config.zone_id}}">
                <button type="submit">Save All Settings</button>
            </form>
        </div>

        <div class="card">
            <h3>💰 Pending Requests (Withdraw & Recharge)</h3>
            <div style="overflow-y: auto; max-height: 400px;">
                <table>
                    <tr><th>User</th><th>Type</th><th>Amount</th><th>Number</th><th>Action</th></tr>
                    {% for w in withdraws %}
                    <tr>
                        <td>{{w.name}}</td>
                        <td style="color:{% if w.type == 'Recharge' %}#8b5cf6{% else %}#f59e0b{% endif %}">{{w.type}}</td>
                        <td>৳{{w.amount}}</td>
                        <td>{{w.account}}</td>
                        <td><a href="/admin/pay/{{w._id}}" style="color:#ef4444;">Paid</a></td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h3>👥 User Management</h3>
        <div style="overflow-x:auto;">
            <table width="100%">
                <tr><th>Name/ID</th><th>Balance</th><th>Action</th></tr>
                {% for u in users %}
                <tr>
                    <form action="/admin/edit_user/{{u.user_id}}" method="post">
                    <td>{{u.name}}<br><small>{{u.user_id}}</small></td>
                    <td><input name="balance" value="{{u.balance}}" style="width:70px;"></td>
                    <td><button type="submit" style="padding:5px;">Update</button></td>
                    </form>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def home():
    user_id, name, ref_by = request.args.get('id'), request.args.get('name', 'User'), request.args.get('ref')
    if not user_id: return "<h1>Join via Bot first!</h1>", 403
    
    config = get_settings()
    user = users_collection.find_one({"user_id": user_id})
    now = datetime.now()
    reset_delta = timedelta(hours=config.get('reset_hours', 24), minutes=config.get('reset_minutes', 0))

    if not user:
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": get_user_ip(), 
                     "referred_by": ref_by, "daily_views": 0, "last_reset_time": now}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != user_id:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data
    
    # Auto Reset Logic
    last_reset = user.get('last_reset_time', now)
    next_reset = last_reset + reset_delta
    if now >= next_reset:
        users_collection.update_one({"user_id": user_id}, {"$set": {"daily_views": 0, "last_reset_time": now}})
        user['daily_views'] = 0
        next_reset = now + reset_delta

    return render_template_string(USER_DASHBOARD, user=user, config=config, next_reset=next_reset.strftime('%Y-%m-%dT%H:%M:%S'))

@app.route('/update_balance', methods=['POST'])
def update_balance():
    uid = request.json.get('user_id')
    config = get_settings()
    user = users_collection.find_one({"user_id": uid})
    if user['daily_views'] >= config['daily_ad_limit']: return jsonify({"success": False, "message": "Limit Reached!"})
    users_collection.update_one({"user_id": uid}, {"$inc": {"balance": config['ad_rate'], "daily_views": 1}})
    return jsonify({"success": True, "new_balance": user['balance'] + config['ad_rate'], "daily_left": config['daily_ad_limit'] - (user['daily_views'] + 1)})

@app.route('/request_payment', methods=['POST'])
def request_payment():
    data = request.json
    config = get_settings()
    user = users_collection.find_one({"user_id": data['user_id']})
    
    min_amt = config['min_recharge'] if data['type'] == 'Recharge' else config['min_withdraw']
    
    if data['amount'] < min_amt or user['balance'] < data['amount']:
        return jsonify({"success": False, "message": "Check Balance or Limit!"})
    
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({
        "user_id": data['user_id'], "name": user['name'], "amount": data['amount'], 
        "account": data['account'], "method": data['method'], "type": data['type'], 
        "status": "Pending", "date": datetime.now()
    })
    return jsonify({"success": True, "message": data['type'] + " Requested Successfully!"})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST' and session.get('logged'):
        try:
            settings_collection.update_one({"id": "config"}, {"$set": {
                "notice": request.form.get('notice'),
                "ad_rate": float(request.form.get('ad_rate')),
                "min_withdraw": float(request.form.get('min_withdraw')),
                "min_recharge": float(request.form.get('min_recharge')),
                "recharge_on": True if request.form.get('recharge_on') == 'on' else False,
                "daily_ad_limit": int(request.form.get('daily_ad_limit')),
                "withdraw_methods": [m.strip() for m in request.form.get('withdraw_methods').split(',')],
                "zone_id": request.form.get('zone_id')
            }})
            return redirect(url_for('admin'))
        except: return "Error saving settings!"
    elif request.method == 'POST' and request.form.get('pass') == ADMIN_PASSWORD_ENV:
        session['logged'] = True
        return redirect(url_for('admin'))
    if not session.get('logged'): return '<body style="background:#0f172a;color:white;text-align:center;padding:100px;"><form method="post"><h2>Login</h2><input name="pass" type="password"><button>Login</button></form></body>'
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
    if session.get('logged'): withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

if __name__ == "__main__":
    if bot:
        bot.remove_webhook()
        threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

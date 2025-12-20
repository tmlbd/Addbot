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
SECRET_KEY = os.environ.get("SECRET_KEY", "PREMIUM_ULTIMATE_MASTER_2025")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Bot Setup
bot = None
BOT_USERNAME = "Bot"
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        bot_user = bot.get_me()
        BOT_USERNAME = bot_user.username
    except:
        BOT_USERNAME = "Bot"

# Database Connection
client = MongoClient(MONGO_URI)
db = client['mega_earning_ultimate_v26']
users_collection = db['users']
settings_collection = db['settings']
withdraws_collection = db['withdrawals']

def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config",
            "ad_count_per_click": 2,
            "ad_interval": 3, 
            "ad_rate": 0.50,
            "ref_commission": 2.00,
            "min_withdraw": 10.00,
            "max_withdraw": 1000.00,
            "min_recharge": 20.00,
            "recharge_on": True,
            "daily_ad_limit": 50,
            "reset_hours": 24,
            "reset_minutes": 0,
            "withdraw_methods": ["Bkash", "Nagad", "Rocket"],
            "recharge_methods": ["GP", "Robi", "Banglalink"],
            "notice": "সঠিক VPN কানেক্ট করে কাজ শুরু করুন।",
            "zone_id": "10351894",
            "vpn_on": False,
            "allowed_countries": "US,GB,CA",
            "app_url": APP_URL_ENV
        }
        settings_collection.insert_one(default)
        return default
    return setts

def get_user_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

def check_vpn_status(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,proxy,hosting", timeout=5).json()
        return {"country": res.get('countryCode'), "is_vpn": res.get('proxy') or res.get('hosting')}
    except: return {"country": "Unknown", "is_vpn": False}

# --- TELEGRAM BOT LOGIC ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        final_url = APP_URL_ENV if APP_URL_ENV else config.get('app_url')
        if not final_url:
            bot.reply_to(message, "❌ ওয়েবসাইট ইউআরএল সেটআপ হয়নি। রেন্ডারে APP_URL যোগ করুন।")
            return

        dashboard_url = f"{final_url}/?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, f"👋 স্বাগতম {name}!\n💰 এড দেখে আয় শুরু করতে নিচের বাটনে ক্লিক করুন।", reply_markup=markup)

# --- USER DASHBOARD (SEQUENTIAL AD FIX) ---
USER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn Pro | Dashboard</title>
    <!-- Monetag SDK -->
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --primary: #6366f1; --success: #10b981; --bg: #0b0f1a; --card: #161e31; --text: #f8fafc; --accent: #f59e0b; }
        body { font-family: 'Outfit', sans-serif; background: var(--bg); color: var(--text); margin: 0; text-align: center; }
        .notice-bar { background: linear-gradient(90deg, #f59e0b, #d97706); color: black; padding: 10px; font-weight: 700; font-size: 13px; }
        .container { max-width: 480px; margin: auto; padding: 20px; box-sizing: border-box; }
        .card { background: var(--card); border-radius: 30px; padding: 25px; box-shadow: 0 20px 40px rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); }
        .avatar { width: 80px; height: 80px; border-radius: 50%; border: 3px solid var(--primary); margin-bottom: 10px; }
        .balance-card { background: linear-gradient(135deg, #6366f1, #4f46e5); border-radius: 20px; padding: 20px; margin: 20px 0; }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .stat-item { background: #334155; padding: 12px; border-radius: 16px; font-size: 12px; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 18px; font-size: 16px; font-weight: 700; cursor: pointer; margin-bottom: 12px; color: white; transition: 0.3s; }
        .btn-work { background: linear-gradient(to right, #10b981, #059669); }
        .btn-withdraw { background: #334155; }
        .btn-recharge { background: #8b5cf6; }
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); }
        .modal-content { background: var(--card); margin: 15% auto; padding: 30px; width: 85%; max-width: 400px; border-radius: 25px; text-align: left; }
        input, select { width: 100%; padding: 14px; margin: 10px 0; border-radius: 12px; background: #0b0f1a; color: white; border: 1px solid #334155; }
    </style>
</head>
<body>
    <div class="notice-bar">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=6366f1&color=fff" class="avatar">
            <h2 style="margin:0;">{{ user.name }}</h2>
            <div class="balance-card">
                <small style="opacity:0.8;">Available Balance</small>
                <div style="font-size: 38px; font-weight: 700;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            <div class="stats-grid">
                <div class="stat-item"><b>{{ user.ref_count }}</b><br>Refers</div>
                <div class="stat-item"><b id="daily_left">{{ config.daily_ad_limit - user.daily_views }}</b><br>Ads Left</div>
            </div>
            <button class="btn btn-work" id="workBtn" onclick="startWork()">WATCH ADS ({{ config.ad_count_per_click }})</button>
            <div style="display:flex; gap:10px;">
                <button class="btn btn-withdraw" onclick="openM('withdrawModal')">CASH OUT</button>
                {% if config.recharge_on %}<button class="btn btn-recharge" onclick="openM('rechargeModal')">RECHARGE</button>{% endif %}
            </div>
            <p style="font-size:11px; color:#64748b;">Next Reset: <span id="timer" style="color:white;">--:--:--</span></p>
        </div>
    </div>

    <!-- Modals -->
    <div id="withdrawModal" class="modal">
        <div class="modal-content">
            <h3>Withdrawal</h3>
            <select id="w_method">{% for m in config.withdraw_methods %}<option value="{{m}}">{{m}}</option>{% endfor %}</select>
            <input type="number" id="w_amount" placeholder="Amount (৳)">
            <input type="text" id="w_account" placeholder="Number">
            <button class="btn btn-work" onclick="submitReq('Withdraw', 'w_method', 'w_amount', 'w_account')">Confirm</button>
            <button class="btn btn-withdraw" onclick="closeM('withdrawModal')">Cancel</button>
        </div>
    </div>

    <div id="rechargeModal" class="modal">
        <div class="modal-content">
            <h3>Mobile Recharge</h3>
            <select id="r_method">{% for r in config.recharge_methods %}<option value="{{r}}">{{r}}</option>{% endfor %}</select>
            <input type="number" id="r_amount" placeholder="Min ৳{{config.min_recharge}}">
            <input type="text" id="r_account" placeholder="Mobile Number">
            <button class="btn btn-recharge" onclick="submitReq('Recharge', 'r_method', 'r_amount', 'r_account')">Confirm Recharge</button>
            <button class="btn btn-withdraw" onclick="closeM('rechargeModal')">Cancel</button>
        </div>
    </div>

    <script>
    function openM(id) { document.getElementById(id).style.display = 'block'; }
    function closeM(id) { document.getElementById(id).style.display = 'none'; }

    function startWork() {
        let left = parseInt(document.getElementById('daily_left').innerText);
        if(left <= 0) return alert("লিমিট শেষ!");
        
        let zid = "{{ config.zone_id }}";
        let totalAds = {{ config.ad_count_per_click }};
        let interval = {{ config.ad_interval }} * 1000;
        
        let adFuncName = 'show_' + zid;
        
        if (window[adFuncName] && typeof window[adFuncName] === 'function') {
            document.getElementById('workBtn').disabled = true;
            document.getElementById('workBtn').innerText = "Ad 1 Loading...";
            
            let adsDone = 0;
            function runAdLoop() {
                if (adsDone < totalAds) {
                    window[adFuncName](); // এড দেখানো
                    adsDone++;
                    if(adsDone < totalAds) {
                        document.getElementById('workBtn').innerText = "Ad " + (adsDone + 1) + " in " + (interval/1000) + "s...";
                        setTimeout(runAdLoop, interval);
                    } else {
                        finishWork();
                    }
                }
            }
            runAdLoop();
        } else { 
            alert("অ্যাড স্ক্রিপ্ট লোড হয়নি! জোন আইডি বা অ্যাড-ব্লকার চেক করুন।"); 
        }
    }

    function finishWork() {
        fetch('/update_balance', {
            method:'POST', headers:{'Content-Type':'application/json'}, 
            body:JSON.stringify({user_id:"{{user.user_id}}"})
        }).then(res=>res.json()).then(data=> {
            document.getElementById('workBtn').disabled = false;
            document.getElementById('workBtn').innerText = "WATCH ADS ({{ config.ad_count_per_click }})";
            if(data.success) {
                document.getElementById('bal').innerText = data.new_balance.toFixed(2);
                location.reload();
            }
        });
    }

    function submitReq(type, mId, aId, accId) {
        let amt = document.getElementById(aId).value;
        let acc = document.getElementById(accId).value;
        let method = document.getElementById(mId).value;
        fetch('/request_payment', {
            method:'POST', headers:{'Content-Type':'application/json'}, 
            body:JSON.stringify({user_id:"{{user.user_id}}", amount:parseFloat(amt), account:acc, method:method, type:type})
        }).then(res=>res.json()).then(data=>{ alert(data.message); location.reload(); });
    }

    function updateTimer() {
        const next = new Date("{{ next_reset }}").getTime();
        const diff = next - new Date().getTime();
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

# --- ADMIN PANEL ---
ADMIN_PANEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Master Admin Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Outfit', sans-serif; background: #0b0f1a; color: white; padding: 20px; }
        .header { background: linear-gradient(135deg, #6366f1, #a855f7); padding: 30px; border-radius: 20px; text-align: center; margin-bottom: 30px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .card { background: #161e31; padding: 25px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05); }
        input, textarea, select { width: 100%; padding: 12px; margin: 8px 0; border-radius: 10px; background: #0b0f1a; color: white; border: 1px solid #334155; box-sizing: border-box; }
        button { background: #10b981; color: white; border: none; padding: 12px; width: 100%; border-radius: 10px; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        th, td { padding: 10px; border-bottom: 1px solid #334155; }
    </style>
</head>
<body>
    <div class="header"><h1>👑 Master Admin Control</h1></div>
    <div class="grid">
        <div class="card">
            <h3>⚙️ App Settings</h3>
            <form method="POST" action="/admin/save_settings">
                Notice: <textarea name="notice">{{config.notice}}</textarea>
                Ad Rate: <input name="ad_rate" step="0.01" value="{{config.ad_rate}}">
                Ads Per Click: <input name="ad_count_per_click" type="number" value="{{config.ad_count_per_click}}">
                Ad Interval (Seconds): <input name="ad_interval" type="number" value="{{config.ad_interval}}">
                Daily Limit: <input name="daily_ad_limit" type="number" value="{{config.daily_ad_limit}}">
                <b>Zone ID:</b> <input name="zone_id" value="{{config.zone_id}}">
                Min Withdraw/Recharge: <div style="display:flex; gap:5px;"><input name="min_withdraw" value="{{config.min_withdraw}}"><input name="min_recharge" value="{{config.min_recharge}}"></div>
                Withdraw Methods: <input name="withdraw_methods" value="{{ config.withdraw_methods|join(', ') }}">
                Sim Methods: <input name="recharge_methods" value="{{ config.recharge_methods|join(', ') }}">
                VPN Status: <select name="vpn_on"><option value="on" {% if config.vpn_on %}selected{% endif %}>ON</option><option value="off" {% if not config.vpn_on %}selected{% endif %}>OFF</option></select>
                Allowed Countries: <input name="allowed_countries" value="{{config.allowed_countries}}">
                <button type="submit">Update Everything</button>
            </form>
        </div>
        <div class="card">
            <h3>💰 Pending Requests</h3>
            <table>
                <tr><th>User</th><th>Type/Amt</th><th>Action</th></tr>
                {% for w in withdraws %}
                <tr><td>{{w.name}}<br><small>{{w.type}}</small></td><td>৳{{w.amount}}</td><td><a href="/admin/pay/{{w._id}}" style="color:red; font-weight:bold;">Paid</a></td></tr>
                {% endfor %}
            </table>
        </div>
    </div>
    <div class="card" style="margin-top:20px;">
        <h3>👥 User Management</h3>
        <div style="overflow-x:auto;">
            <table>
                <tr><th>Name/ID</th><th>Balance</th><th>Daily Views</th><th>Refers</th><th>Action</th></tr>
                {% for u in users %}
                <tr>
                    <form action="/admin/edit_user/{{u.user_id}}" method="POST">
                    <td>{{u.name}}<br><small>#{{u.user_id}}</small></td>
                    <td><input name="balance" value="{{u.balance}}" style="width:70px; margin:0;"></td>
                    <td><input name="daily_views" value="{{u.daily_views}}" style="width:40px; margin:0;"></td>
                    <td><input name="ref_count" value="{{u.ref_count}}" style="width:40px; margin:0;"></td>
                    <td><button type="submit" style="padding:5px; width:auto;">Save</button></td>
                    </form>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
    <br><center><a href="/logout" style="color:red; text-decoration:none; font-weight:bold;">Logout Admin</a></center>
</body>
</html>
"""

# --- BACKEND ROUTES ---
@app.route('/')
def home():
    user_id, name, ref_by = request.args.get('id'), request.args.get('name', 'User'), request.args.get('ref')
    if not user_id: return "<h1>Please Join via Bot!</h1>", 403
    config = get_settings()
    ip = get_user_ip()
    now = datetime.now()
    reset_delta = timedelta(hours=config.get('reset_hours', 24))

    if config['vpn_on']:
        ip_info = check_vpn_status(ip)
        allowed = [c.strip() for c in config['allowed_countries'].split(',')]
        if ip_info['country'] not in allowed:
            return f"<body style='background:#0b0f1a;color:white;text-align:center;padding:50px;'><h1>VPN Required! ❌</h1><p>Allowed: {config['allowed_countries']}</p></body>"

    if not config.get('app_url'):
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": request.host_url.rstrip('/')}})

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, 
                     "referred_by": ref_by, "daily_views": 0, "last_reset_time": now}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != user_id:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data
    
    last_reset = user.get('last_reset_time', now)
    next_reset = last_reset + reset_delta
    if now >= next_reset:
        users_collection.update_one({"user_id": user_id}, {"$set": {"daily_views": 0, "last_reset_time": now}})
        user['daily_views'] = 0
        next_reset = now + reset_delta

    return render_template_string(USER_DASHBOARD, user=user, config=config, bot_username=BOT_USERNAME, next_reset=next_reset.strftime('%Y-%m-%dT%H:%M:%S'))

@app.route('/update_balance', methods=['POST'])
def update_balance():
    uid = request.json.get('user_id')
    config = get_settings()
    user = users_collection.find_one({"user_id": uid})
    if user['daily_views'] >= config['daily_ad_limit']: return jsonify({"success": False, "message": "Limit Reached!"})
    users_collection.update_one({"user_id": uid}, {"$inc": {"balance": config['ad_rate'], "daily_views": 1}})
    u = users_collection.find_one({"user_id": uid})
    return jsonify({"success": True, "new_balance": u['balance']})

@app.route('/request_payment', methods=['POST'])
def request_payment():
    data = request.json
    config = get_settings()
    user = users_collection.find_one({"user_id": data['user_id']})
    min_amt = config['min_recharge'] if data['type'] == 'Recharge' else config['min_withdraw']
    if data['amount'] < min_amt or user['balance'] < data['amount']:
        return jsonify({"success": False, "message": "Balance check failed!"})
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "method": data['method'], "type": data['type'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Request Submitted!"})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if request.form.get('pass') == ADMIN_PASSWORD_ENV:
            session['logged'] = True
            return redirect(url_for('admin'))
    if not session.get('logged'): return '<body style="background:#0b0f1a;color:white;text-align:center;padding:100px;"><h2>Admin Login</h2><form method="POST"><input name="pass" type="password" style="padding:10px;"><br><br><button type="submit">Login</button></form></body>'
    
    users = list(users_collection.find().limit(100))
    withdraws = list(withdraws_collection.find({"status": "Pending"}))
    return render_template_string(ADMIN_PANEL, config=config, users=users, withdraws=withdraws)

@app.route('/admin/save_settings', methods=['POST'])
def save_settings():
    if session.get('logged'):
        try:
            settings_collection.update_one({"id": "config"}, {"$set": {
                "notice": request.form.get('notice'), "ad_rate": float(request.form.get('ad_rate')),
                "ad_count_per_click": int(request.form.get('ad_count_per_click')), "ad_interval": int(request.form.get('ad_interval')),
                "min_withdraw": float(request.form.get('min_withdraw')), "min_recharge": float(request.form.get('min_recharge')),
                "daily_ad_limit": int(request.form.get('daily_ad_limit')), "zone_id": request.form.get('zone_id'),
                "withdraw_methods": [m.strip() for m in request.form.get('withdraw_methods').split(',')],
                "recharge_methods": [r.strip() for r in request.form.get('recharge_methods').split(',')],
                "vpn_on": True if request.form.get('vpn_on') == 'on' else False,
                "allowed_countries": request.form.get('allowed_countries')
            }}, upsert=True)
        except: pass
    return redirect(url_for('admin'))

@app.route('/admin/edit_user/<uid>', methods=['POST'])
def edit_user(uid):
    if session.get('logged'):
        users_collection.update_one({"user_id": uid}, {"$set": {
            "balance": float(request.form.get('balance', 0)),
            "daily_views": int(request.form.get('daily_views', 0)),
            "ref_count": int(request.form.get('ref_count', 0))
        }})
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

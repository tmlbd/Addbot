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
        me = bot.get_me()
        BOT_USERNAME = me.username
        print(f"✅ Bot Connected: @{BOT_USERNAME}")
    except:
        print("❌ Bot Token Invalid!")

# Database Connection
client = MongoClient(MONGO_URI)
db = client['mega_earning_final_v100_secure']
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
            "min_withdraw": 50.00,
            "max_withdraw": 1000.00,
            "min_recharge": 20.00,
            "recharge_on": True,
            "daily_ad_limit": 50,
            "reset_hours": 24,
            "withdraw_methods": ["Bkash", "Nagad", "Rocket"],
            "recharge_methods": ["GP", "Robi", "Airtel", "Banglalink"],
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
        
        user = users_collection.find_one({"user_id": uid})
        balance = user['balance'] if user else 0.0
        ref_count = user['ref_count'] if user else 0
        
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        final_url = APP_URL_ENV if APP_URL_ENV else config.get('app_url')
        
        if not final_url:
            bot.reply_to(message, "❌ Admin: Please set APP_URL in Render Variables.")
            return

        dashboard_url = f"{final_url}/?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        msg = (
            f"🚀 **স্বাগতম, {name}!**\n\n"
            f"📊 **আপনার তথ্য:**\n"
            f"🆔 আইডি: `{uid}`\n"
            f"💰 ব্যালেন্স: `{balance:.2f}` ৳\n"
            f"👥 মোট রেফার: `{ref_count}` জন\n\n"
            f"📢 **নোটিশ:** {config['notice']}\n"
        )
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, msg, reply_markup=markup, parse_mode="Markdown")

# --- USER DASHBOARD ---
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
        :root { --primary: #6366f1; --success: #10b981; --bg: #0b0f1a; --card: #161e31; --text: #f8fafc; }
        body { font-family: 'Outfit', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; flex-direction: column; align-items: center; }
        .notice-bar { background: linear-gradient(90deg, #f59e0b, #d97706); color: #000; width: 100%; padding: 12px; font-weight: 700; font-size: 13px; text-align: center; }
        .container { width: 100%; max-width: 450px; padding: 20px; box-sizing: border-box; }
        .glass-card { background: var(--card); border-radius: 30px; padding: 30px; border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 25px 50px rgba(0,0,0,0.5); text-align: center; }
        .avatar { width: 80px; height: 80px; border-radius: 50%; border: 3px solid var(--primary); margin-bottom: 10px; }
        .balance-card { background: linear-gradient(135deg, #6366f1, #a855f7); border-radius: 20px; padding: 25px; margin: 20px 0; }
        .balance-amount { font-size: 38px; font-weight: 700; display: block; }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }
        .stat-box { background: rgba(255,255,255,0.03); padding: 15px; border-radius: 20px; }
        .btn { width: 100%; padding: 18px; border: none; border-radius: 20px; font-size: 17px; font-weight: 700; cursor: pointer; transition: 0.3s; margin-bottom: 12px; color: #fff; }
        .btn-work { background: linear-gradient(to right, #10b981, #059669); }
        .btn-withdraw { background: #1e293b; }
        .btn-recharge { background: #8b5cf6; }
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); }
        .modal-content { background: #161e31; margin: 15% auto; padding: 30px; width: 85%; max-width: 380px; border-radius: 25px; border: 1px solid #334155; }
        input, select { width: 100%; padding: 14px; margin: 10px 0; border-radius: 12px; background: #0b0f1a; color: #fff; border: 1px solid #334155; }
    </style>
</head>
<body>
    <div class="notice-bar">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="glass-card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=6366f1&color=fff&bold=true" class="avatar">
            <h2 style="margin:0;">{{ user.name }}</h2>
            <div class="balance-card">
                <small style="opacity:0.8;">Available Balance</small>
                <div style="font-size: 38px; font-weight: 700;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            <div class="stats-grid">
                <div class="stat-box"><small>Refers</small><div>{{ user.ref_count }}</div></div>
                <div class="stat-box"><small>Ads Left</small><div id="daily_left">{{ config.daily_ad_limit - user.daily_views }}</div></div>
            </div>
            <button class="btn btn-work" id="workBtn" onclick="startAutoWork()">WATCH ADS ({{ config.ad_count_per_click }})</button>
            <div style="display:flex; gap:10px;">
                <button class="btn btn-withdraw" onclick="openM('withdrawModal')">WITHDRAW</button>
                {% if config.recharge_on %}<button class="btn btn-recharge" onclick="openM('rechargeModal')">RECHARGE</button>{% endif %}
            </div>
            <div style="background:#000; padding:12px; border-radius:15px; font-size:10px; color:#3b82f6; margin-top:15px; border:1px solid #1e293b; text-align:left;">
                <b>Refer Link:</b><br>
                https://t.me/{{ bot_username }}?start={{ user.user_id }}
            </div>
            <p style="font-size:11px; color:#64748b; margin-top:15px;">Next Reset In: <span id="timer" style="color:#fff;">--:--:--</span></p>
        </div>
    </div>

    <!-- Modals -->
    <div id="withdrawModal" class="modal">
        <div class="modal-content">
            <h3>Withdraw Money</h3>
            <select id="w_method">{% for m in config.withdraw_methods %}<option value="{{m}}">{{m}}</option>{% endfor %}</select>
            <input type="number" id="w_amount" placeholder="Amount">
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
            <input type="text" id="r_account" placeholder="Phone Number">
            <button class="btn btn-recharge" onclick="submitReq('Recharge', 'r_method', 'r_amount', 'r_account')">Confirm</button>
            <button class="btn btn-withdraw" onclick="closeM('rechargeModal')">Cancel</button>
        </div>
    </div>

    <script>
    function openM(id) { document.getElementById(id).style.display = 'block'; }
    function closeM(id) { document.getElementById(id).style.display = 'none'; }

    function startAutoWork() {
        let left = parseInt(document.getElementById('daily_left').innerText);
        if(left <= 0) return alert("Daily limit reached!");
        
        let zid = "{{ config.zone_id }}";
        let totalAds = {{ config.ad_count_per_click }};
        let interval = {{ config.ad_interval }} * 1000;
        
        let adFunc = window['show_'+zid];
        
        if (typeof adFunc === 'function') {
            document.getElementById('workBtn').disabled = true;
            document.getElementById('workBtn').innerText = "Loading Ads...";
            
            let adsDone = 0;
            function runLoop() {
                if (adsDone < totalAds) {
                    adFunc(); 
                    adsDone++;
                    if(adsDone < totalAds) {
                        document.getElementById('workBtn').innerText = "Next Ad in " + (interval/1000) + "s...";
                        setTimeout(runLoop, interval);
                    } else {
                        finishWork();
                    }
                }
            }
            runLoop();
        } else { 
            alert("Ad script not loaded! Please check AdBlocker.");
            document.getElementById('workBtn').disabled = false;
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
        .card { background: #161e31; padding: 20px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05); }
        input, textarea, select { width: 100%; padding: 12px; margin: 8px 0; border-radius: 10px; background: #0b0f1a; color: white; border: 1px solid #334155; }
        button { background: #10b981; color: white; border: none; padding: 12px; width: 100%; border-radius: 10px; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 12px; }
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
                Min Withdraw: <input name="min_withdraw" value="{{config.min_withdraw}}">
                Min Recharge: <input name="min_recharge" value="{{config.min_recharge}}">
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
    <br><center><a href="/logout" style="color:red; text-decoration:none; font-weight:bold;">Logout</a></center>
</body>
</html>
"""

# --- BACKEND ROUTES ---
@app.route('/')
def home():
    user_id, name, ref_by = request.args.get('id'), request.args.get('name', 'User'), request.args.get('ref')
    if not user_id: return "<h1>Join via Bot first!</h1>", 403
    
    config = get_settings()
    ip = get_user_ip()
    now = datetime.now()
    reset_delta = timedelta(hours=config.get('reset_hours', 24))

    # VPN Checking
    if config['vpn_on']:
        ip_info = check_vpn_status(ip)
        allowed = [c.strip() for c in config['allowed_countries'].split(',')]
        if ip_info['country'] not in allowed:
            return f"<body style='background:#0b0f1a;color:white;text-align:center;padding:50px;'><h1>VPN Required! ❌</h1><p>Allowed: {config['allowed_countries']}</p></body>"

    if not config.get('app_url'):
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": request.host_url.rstrip('/')}})

    user_by_id = users_collection.find_one({"user_id": user_id})
    
    # --- Strict IP Check System ---
    if not user_by_id:
        # ইউজার নতুন হলে চেক করো তার আইপি দিয়ে আগে কেউ একাউন্ট করেছে কি না
        existing_ip_user = users_collection.find_one({"ip_address": ip})
        if existing_ip_user:
            return f"<body style='background:#0b0f1a;color:white;text-align:center;padding:50px;'><h1>Access Denied! ⚠️</h1><p>একাধিক আইডি চালানো নিষিদ্ধ। এই ডিভাইস/নেটওয়ার্ক দিয়ে আগে একাউন্ট খোলা হয়েছে।</p></body>", 403
        
        # নতুন ইউজার তৈরি
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, 
                     "referred_by": ref_by, "daily_views": 0, "last_reset_time": now}
        users_collection.insert_one(user_data)
        
        # রেফারেল কমিশন
        if ref_by and ref_by != user_id:
            # চেক করা হচ্ছে রেফারার এবং নতুন ইউজার এক আইপি কি না (রেফারেল জালিয়াতি রোধ)
            ref_user_data = users_collection.find_one({"user_id": ref_by})
            if ref_user_data and ref_user_data.get('ip_address') != ip:
                users_collection.update_one(
                    {"user_id": ref_by}, 
                    {"$inc": {"balance": config['ref_commission'], "ref_count": 1}}
                )
        user = user_data
    else:
        user = user_by_id
    
    # Auto Reset Check
    if now >= user.get('last_reset_time', now) + reset_delta:
        users_collection.update_one({"user_id": user_id}, {"$set": {"daily_views": 0, "last_reset_time": now}})
        user['daily_views'] = 0

    return render_template_string(USER_DASHBOARD, user=user, config=config, bot_username=BOT_USERNAME, next_reset=(user.get('last_reset_time', now) + reset_delta).strftime('%Y-%m-%dT%H:%M:%S'))

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
        return jsonify({"success": False, "message": "Check Balance or Limit!"})
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "method": data['method'], "type": data['type'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Request Submitted Successfully!"})

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

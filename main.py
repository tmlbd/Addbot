import os
import threading
import time
import requests
import telebot
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

# --- ভেরিয়েবল কনফিগারেশন (Environment Variables) ---
MONGO_URI = os.environ.get("MONGO_URI")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASS", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "FINAL_MASTER_PRO_2025")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# টেলিগ্রাম বট ইনিশিয়ালাইজেশন
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# --- ডাটাবেস কানেকশন ---
try:
    client = MongoClient(MONGO_URI)
    db = client['integrated_mega_earning_db']
    users_collection = db['users']
    settings_collection = db['settings']
    withdraws_collection = db['withdrawals']
    print("✅ Database Connected Successfully!")
except Exception as e:
    print(f"❌ Database Error: {e}")

# সেটিংস লোড বা তৈরি
def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config", 
            "ad_count": 1, 
            "ad_rate": 0.50, 
            "ref_commission": 2.00,
            "min_withdraw": 10.00, 
            "max_withdraw": 1000.00, 
            "withdraw_methods": ["Bkash", "Nagad", "Rocket"],
            "notice": "সঠিক VPN কানেক্ট করে কাজ করুন!", 
            "zone_id": "10341337", 
            "vpn_on": False, 
            "allowed_countries": "US,GB,CA", 
            "app_url": ""
        }
        settings_collection.insert_one(default)
        return default
    return setts

def get_user_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

def check_vpn_status(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,proxy,hosting", timeout=5).json()
        if res.get('status') == 'success':
            return {"country": res.get('countryCode'), "is_vpn": res.get('proxy') or res.get('hosting')}
    except: pass
    return {"country": "Unknown", "is_vpn": False}

# --- টেলিগ্রাম বট লজিক ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        # ইউআরএল ডিটেকশন (যদি ডাটাবেসে না থাকে তবে কারেন্ট হোস্ট নিবে)
        base_url = config.get('app_url') if config.get('app_url') else "https://" + request.host
        dashboard_url = f"{base_url}/?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, f"👋 স্বাগতম {name}!\n💰 এড দেখে আয় শুরু করতে নিচের বাটনে ক্লিক করুন।\n\n📢 নোটিশ: {config['notice']}", reply_markup=markup)

# --- ইউজার ড্যাশবোর্ড (ডিজাইন) ---
USER_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard</title>
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <style>
        body { font-family: 'Poppins', sans-serif; background: #0f172a; color: white; margin: 0; text-align: center; }
        .notice { background: #f59e0b; color: black; padding: 10px; font-weight: bold; font-size: 13px; }
        .container { padding: 20px; max-width: 450px; margin: auto; }
        .card { background: #1e293b; border-radius: 20px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .balance-box { background: linear-gradient(135deg, #3b82f6, #2563eb); padding: 20px; border-radius: 15px; margin: 15px 0; }
        .btn { width: 100%; padding: 15px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 10px; color: white; }
        .info { font-size: 12px; color: #94a3b8; text-align: left; margin-top: 20px; background: #334155; padding: 10px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="notice">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=3b82f6&color=fff" style="width:75px; border-radius:50%; border:3px solid #3b82f6;">
            <h3 style="margin:10px 0;">{{ user.name }}</h3>
            <div class="balance-box">
                <small>Available Balance</small>
                <div style="font-size: 34px; font-weight: bold;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            <button class="btn" style="background:#10b981;" onclick="startWork()">WATCH ADS</button>
            <button class="btn" style="background:#f59e0b;" onclick="openW()">WITHDRAW</button>
            <div class="info">
                🆔 User ID: {{ user.user_id }}<br>
                👥 Total Refers: {{ user.ref_count }}<br>
                💰 Limits: ৳{{ config.min_withdraw }} - ৳{{ config.max_withdraw }}
            </div>
            <p style="font-size:10px; color:#64748b; margin-top:10px;">Ref Link: t.me/{{ bot_username }}?start={{ user.user_id }}</p>
        </div>
    </div>
    <script>
    function startWork() {
        let zid = "{{ config.zone_id }}";
        if(typeof window['show_'+zid] === 'function') {
            for(let i=0; i< {{config.ad_count}}; i++){ window['show_'+zid](); }
            fetch('/update_balance', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:"{{user.user_id}}"})})
            .then(res=>res.json()).then(data=> { if(data.success) document.getElementById('bal').innerText = data.new_balance.toFixed(2); });
        } else { alert("AdBlocker বন্ধ করুন!"); }
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

# --- প্রিমিয়াম এডমিন প্যানেল (ডিজাইন) ---
ADMIN_PANEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: white; padding: 20px; }
        .header { background: linear-gradient(90deg, #6366f1, #a855f7); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 25px; }
        .card { background: #1e293b; border-radius: 15px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }
        input, select, textarea { width: 100%; padding: 12px; margin: 8px 0; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: white; box-sizing: border-box; }
        button { background: #10b981; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; }
        table { width: 100%; border-collapse: collapse; background: #1e293b; }
        th, td { padding: 12px; border: 1px solid #334155; text-align: left; }
        .btn-update { background: #3b82f6; padding: 5px 10px; width: auto; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header"><h1>💎 Admin Master Dashboard</h1></div>
    
    <div class="card">
        <h3>⚙️ Global Configuration</h3>
        <form method="post">
            Notice: <textarea name="notice">{{config.notice}}</textarea>
            Monetag Zone ID: <input name="zone_id" value="{{config.zone_id}}">
            Ad Rate: <input name="ad_rate" step="0.01" value="{{config.ad_rate}}">
            Ads/Click: <input name="ad_count" type="number" value="{{config.ad_count}}">
            Ref Bonus: <input name="ref_commission" step="0.01" value="{{config.ref_commission}}">
            Min Withdraw: <input name="min_withdraw" value="{{config.min_withdraw}}">
            Max Withdraw: <input name="max_withdraw" value="{{config.max_withdraw}}">
            VPN Status: <select name="vpn_on">
                <option value="on" {% if config.vpn_on %}selected{% endif %}>Enabled (ON)</option>
                <option value="off" {% if not config.vpn_on %}selected{% endif %}>Disabled (OFF)</option>
            </select>
            Allowed Countries: <input name="allowed_countries" value="{{config.allowed_countries}}" placeholder="US,GB,CA">
            <button type="submit">Update All Settings</button>
        </form>
    </div>

    <div class="card">
        <h3>💰 Pending Withdrawals</h3>
        <table>
            <tr><th>Name</th><th>Amount</th><th>Wallet</th><th>Action</th></tr>
            {% for w in withdraws %}
            <tr>
                <td>{{w.name}}</td><td>৳{{w.amount}}</td><td>{{w.account}}</td>
                <td><a href="/admin/pay/{{w._id}}"><button style="background:red;">Paid</button></a></td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="card">
        <h3>👥 User Management</h3>
        <div style="overflow-x:auto;">
            <table>
                <tr><th>Name/ID</th><th>Balance</th><th>Refers</th><th>Action</th></tr>
                {% for u in users %}
                <tr>
                    <form action="/admin/edit_user/{{u.user_id}}" method="post">
                        <td><small>{{u.user_id}}</small><br><input name="name" value="{{u.name}}" style="margin:0; padding:5px;"></td>
                        <td><input name="balance" step="0.01" value="{{u.balance}}" style="width:70px; margin:0; padding:5px;"></td>
                        <td><input name="ref_count" type="number" value="{{u.ref_count}}" style="width:50px; margin:0; padding:5px;"></td>
                        <td><button type="submit" class="btn-update">Save</button></td>
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
    user_id = request.args.get('id')
    name = request.args.get('name', 'User')
    ref_by = request.args.get('ref')
    
    if not user_id:
        return "<h1>Join via Telegram Bot first!</h1>", 403
    
    config = get_settings()
    # অটো-ইউআরএল ডিটেকশন ফিক্স
    current_url = request.host_url.rstrip('/')
    if config.get('app_url') != current_url:
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": current_url}})
    
    ip = get_user_ip()
    if config['vpn_on']:
        ip_info = check_vpn_status(ip)
        allowed = [c.strip() for c in config['allowed_countries'].split(',')]
        if ip_info['country'] not in allowed:
            return f"<h1>VPN Required! ❌</h1><p>Connect to: {config['allowed_countries']}</p>", 403

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        ip_exists = users_collection.find_one({"ip_address": ip})
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, "referred_by": ref_by, "created_at": datetime.now()}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != user_id and not ip_exists:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data
    
    bot_username = bot.get_me().username if bot else "Bot"
    return render_template_string(USER_DASHBOARD, user=user, config=config, bot_username=bot_username)

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
    if data['amount'] < config['min_withdraw'] or data['amount'] > config['max_withdraw'] or user['balance'] < data['amount']:
        return jsonify({"success": False, "message": "Check Balance/Limit!"})
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Withdrawal requested!"})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if session.get('logged'):
            vpn = True if request.form.get('vpn_on') == 'on' else False
            settings_collection.update_one({"id": "config"}, {"$set": {
                "ad_rate": float(request.form.get('ad_rate')), "ref_commission": float(request.form.get('ref_commission')),
                "min_withdraw": float(request.form.get('min_withdraw')), "max_withdraw": float(request.form.get('max_withdraw')),
                "notice": request.form.get('notice'), "ad_count": int(request.form.get('ad_count')),
                "zone_id": request.form.get('zone_id'), "vpn_on": vpn, "allowed_countries": request.form.get('allowed_countries')
            }})
            return redirect(url_for('admin'))
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
        users_collection.update_one({"user_id": uid}, {"$set": {
            "name": request.form.get('name'), 
            "balance": float(request.form.get('balance')), 
            "ref_count": int(request.form.get('ref_count'))
        }})
    return redirect(url_for('admin'))

@app.route('/admin/pay/<wid>')
def pay_withdraw(wid):
    if session.get('logged'):
        withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('logged', None); return redirect(url_for('admin'))

if __name__ == "__main__":
    if bot:
        # Conflict 409 ফিক্স
        bot.remove_webhook()
        threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True), daemon=True).start()
    
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

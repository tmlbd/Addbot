import os
import threading
import time
import requests
import telebot
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

# --- CONFIG ---
MONGO_URI = os.environ.get("MONGO_URI")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASS", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "EARN_PRO_FIXED_2025")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Bot Setup
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# Database
try:
    client = MongoClient(MONGO_URI)
    db = client['mega_earning_app']
    users_collection = db['users']
    settings_collection = db['settings']
    withdraws_collection = db['withdrawals']
    print("✅ Database Connected!")
except Exception as e:
    print(f"❌ Database Error: {e}")

def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config", "ad_count": 1, "ad_rate": 0.50, "ref_commission": 2.00,
            "min_withdraw": 10.00, "max_withdraw": 1000.00, "withdraw_methods": ["Bkash", "Nagad", "Rocket"],
            "notice": "সঠিক VPN কানেক্ট করে কাজ করুন!", "zone_id": "10341337", 
            "vpn_on": False, "allowed_countries": "US,GB,CA", "app_url": ""
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

# --- TELEGRAM BOT ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        base_url = config.get('app_url') if config.get('app_url') else request.host_url
        dashboard_url = f"{base_url}?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, f"👋 স্বাগতম {name}!\n💰 এড দেখে আয় শুরু করতে নিচের বাটনে ক্লিক করুন।", reply_markup=markup)

# --- USER DASHBOARD (HTML) ---
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
        .card { background: #1e293b; border-radius: 20px; padding: 20px; box-shadow: 0 10px 20px rgba(0,0,0,0.4); }
        .balance-box { background: linear-gradient(135deg, #10b981, #059669); padding: 20px; border-radius: 15px; margin: 15px 0; }
        .btn { width: 100%; padding: 15px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 10px; color: white; }
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
                <div style="font-size: 32px; font-weight: bold;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            <button class="btn" style="background:#3b82f6;" onclick="startWork()">WATCH ADS</button>
            <button class="btn" style="background:#f59e0b;" onclick="openW()">WITHDRAW</button>
            <p style="font-size:12px; color:#94a3b8; margin-top:15px;">ID: {{ user.user_id }} | Ref: {{ user.ref_count }}</p>
        </div>
    </div>
    <script>
    function startWork() {
        let zid = "{{ config.zone_id }}";
        if(typeof window['show_'+zid] === 'function') {
            for(let i=0; i< {{config.ad_count}}; i++){ window['show_'+zid](); }
            fetch('/update_balance', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:"{{user.user_id}}"})})
            .then(res=>res.json()).then(data=> { if(data.success) document.getElementById('bal').innerText = data.new_balance.toFixed(2); });
        } else { alert("Disable AdBlocker!"); }
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

# --- VIBRANT ADMIN PANEL (DESIGNED) ---
ADMIN_PANEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel | Premium</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        :root { --primary: #6366f1; --secondary: #a855f7; --dark: #0f172a; --card: #1e293b; }
        body { font-family: 'Inter', sans-serif; background: var(--dark); color: #f1f5f9; margin: 0; padding: 20px; }
        .header { background: linear-gradient(90deg, var(--primary), var(--secondary)); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 25px; box-shadow: 0 10px 20px rgba(0,0,0,0.3); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: var(--card); border-radius: 15px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid #334155; }
        h3 { border-bottom: 2px solid var(--primary); padding-bottom: 10px; margin-top: 0; color: #818cf8; }
        input, textarea, select { width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: white; box-sizing: border-box; }
        button { background: linear-gradient(to right, #10b981, #3b82f6); color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }
        .btn-pay { background: #ef4444; padding: 5px 10px; font-size: 12px; }
        .btn-edit { background: #3b82f6; padding: 5px 10px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>💎 Premium Admin Master</h1>
        <p>Manage Users, Settings & Withdrawals</p>
    </div>
    
    <div class="grid">
        <!-- Settings -->
        <div class="card">
            <h3>⚙️ App Settings</h3>
            <form method="post">
                <label>Notice Bar:</label>
                <textarea name="notice">{{config.notice}}</textarea>
                <label>Ad Rate (৳):</label>
                <input name="ad_rate" type="number" step="0.01" value="{{config.ad_rate}}">
                <label>Ads per Click:</label>
                <input name="ad_count" type="number" value="{{config.ad_count}}">
                <label>Monetag Zone ID:</label>
                <input name="zone_id" value="{{config.zone_id}}">
                <label>Ref Bonus:</label>
                <input name="ref_commission" type="number" value="{{config.ref_commission}}">
                <label>VPN Status:</label>
                <select name="vpn_on">
                    <option value="on" {% if config.vpn_on %}selected{% endif %}>Enabled (ON)</option>
                    <option value="off" {% if not config.vpn_on %}selected{% endif %}>Disabled (OFF)</option>
                </select>
                <button type="submit">Save All Settings</button>
            </form>
        </div>

        <!-- Withdraws -->
        <div class="card">
            <h3>💰 Pending Withdrawals</h3>
            <div style="overflow-x:auto;">
                <table>
                    <tr><th>User</th><th>Amount</th><th>Action</th></tr>
                    {% for w in withdraws %}
                    <tr>
                        <td>{{w.name}}<br><small>{{w.account}}</small></td>
                        <td>৳{{w.amount}}</td>
                        <td><a href="/admin/pay/{{w._id}}"><button class="btn-pay">Paid</button></a></td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
    </div>

    <div class="card" style="margin-top:20px;">
        <h3>👥 User Management</h3>
        <div style="overflow-x:auto;">
            <table>
                <tr><th>Name/ID</th><th>Balance</th><th>Refers</th><th>Action</th></tr>
                {% for u in users %}
                <tr>
                    <form action="/admin/edit_user/{{u.user_id}}" method="post">
                        <td>{{u.user_id}}<br><input name="name" value="{{u.name}}" style="margin:0;"></td>
                        <td><input name="balance" type="number" step="0.01" value="{{u.balance}}" style="margin:0;"></td>
                        <td><input name="ref_count" type="number" value="{{u.ref_count}}" style="margin:0;"></td>
                        <td><button type="submit" class="btn-edit">Update</button></td>
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
        return "<h1>Access Denied! Use Bot link.</h1>", 403
    
    config = get_settings()
    
    # Auto-save App URL for the first time
    if not config.get('app_url'):
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": request.host_url}})
    
    ip = get_user_ip()
    if config['vpn_on']:
        ip_info = check_vpn_status(ip)
        allowed = [c.strip() for c in config['allowed_countries'].split(',')]
        if ip_info['country'] not in allowed:
            return f"<h1>VPN Required!</h1><p>Connect to: {config['allowed_countries']}</p>", 403

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        ip_exists = users_collection.find_one({"ip_address": ip})
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, "referred_by": ref_by, "created_at": datetime.now()}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != user_id and not ip_exists:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data
    
    return render_template_string(USER_DASHBOARD, user=user, config=config)

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
                "zone_id": request.form.get('zone_id'), "vpn_on": vpn
            }})
            return redirect(url_for('admin'))
        elif request.form.get('pass') == ADMIN_PASSWORD_ENV:
            session['logged'] = True
            return redirect(url_for('admin'))
    
    if not session.get('logged'):
        return '<body style="background:#0f172a;color:white;text-align:center;padding:100px;"><form method="post"><h2>Admin Login</h2><input name="pass" type="password" style="padding:10px;border-radius:5px;"><br><br><button type="submit" style="padding:10px 20px;">Login</button></form></body>'
    
    users = list(users_collection.find().limit(50))
    withdraws = list(withdraws_collection.find({"status": "Pending"}))
    return render_template_string(ADMIN_PANEL, config=config, users=users, withdraws=withdraws)

@app.route('/admin/edit_user/<uid>', methods=['POST'])
def edit_user(uid):
    if session.get('logged'):
        users_collection.update_one({"user_id": uid}, {"$set": {"name": request.form.get('name'), "balance": float(request.form.get('balance')), "ref_count": int(request.form.get('ref_count'))}})
    return redirect(url_for('admin'))

@app.route('/admin/pay/<wid>')
def pay_withdraw(wid):
    if session.get('logged'):
        withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

if __name__ == "__main__":
    if bot: threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

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
SECRET_KEY = os.environ.get("SECRET_KEY", "EARN_PRO_MASTER_2025")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# টেলিগ্রাম বট ইনিশিয়ালাইজেশন
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# --- ডাটাবেস কানেকশন ---
try:
    client = MongoClient(MONGO_URI)
    db = client['master_earning_app']
    users_collection = db['users']
    settings_collection = db['settings']
    withdraws_collection = db['withdrawals']
    print("✅ Database Connected Successfully!")
except Exception as e:
    print(f"❌ Database Error: {e}")

# সেটিংস লোড করা (এডমিন থেকে কন্ট্রোলযোগ্য)
def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config", "ad_count": 1, "ad_rate": 0.50, "ref_commission": 2.00,
            "min_withdraw": 10.00, "max_withdraw": 1000.00, "withdraw_methods": ["Bkash", "Nagad", "Rocket"],
            "notice": "সঠিক VPN কানেক্ট করে কাজ করুন এবং বেশি রেফার করুন!",
            "zone_id": "10341337", "vpn_on": False, "allowed_countries": "US,GB,CA", "app_url": ""
        }
        settings_collection.insert_one(default)
        return default
    return setts

# আইপি ও ভিপিএন চেক
def check_vpn_status(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,proxy,hosting", timeout=5).json()
        if res.get('status') == 'success':
            return {"country": res.get('countryCode'), "is_vpn": res.get('proxy') or res.get('hosting')}
    except: pass
    return {"country": "Unknown", "is_vpn": False}

def get_user_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

# সাইট সজাগ রাখার সিস্টেম (Self-Ping)
def keep_alive():
    while True:
        try:
            config = get_settings()
            if config.get('app_url'): requests.get(config.get('app_url'), timeout=10)
        except: pass
        time.sleep(600)

# --- টেলিগ্রাম বট লজিক ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        if not config.get('app_url'):
            bot.reply_to(message, "❌ ওয়েবসাইট ইউআরএল এখনো ডিটেক্ট হয়নি। একবার হোমপেজ ভিজিট করুন।")
            return

        dashboard_url = f"{config['app_url']}?id={uid}&name={name}"
        if ref_by: dashboard_url += f"&ref={ref_by}"

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="🚀 ওপেন ড্যাশবোর্ড", url=dashboard_url))
        bot.send_message(message.chat.id, f"👋 স্বাগতম {name}!\n💰 এড দেখে আয় করতে নিচের বাটনে ক্লিক করুন।", reply_markup=markup)

# --- ওয়েব ড্যাশবোর্ড (HTML & CSS) ---
USER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn Pro | Dashboard</title>
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: white; margin: 0; text-align: center; }
        .notice { background: #f59e0b; color: black; padding: 12px; font-weight: bold; font-size: 13px; }
        .container { padding: 15px; max-width: 450px; margin: auto; }
        .card { background: #1e293b; border-radius: 20px; padding: 25px; box-shadow: 0 10px 20px rgba(0,0,0,0.4); }
        .profile { margin-bottom: 20px; }
        .profile img { width: 70px; border-radius: 50%; border: 3px solid #3b82f6; }
        .balance-box { background: linear-gradient(135deg, #10b981, #059669); padding: 20px; border-radius: 15px; margin: 15px 0; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .btn-work { background: #3b82f6; color: white; }
        .btn-withdraw { background: #f59e0b; color: white; }
        .info { font-size: 12px; color: #94a3b8; text-align: left; margin-top: 15px; }
        .ref-link { background: #020617; padding: 10px; border-radius: 8px; margin-top: 10px; font-size: 11px; word-break: break-all; color: #60a5fa; }
    </style>
</head>
<body>
    <div class="notice">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <div class="profile">
                <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=3b82f6&color=fff">
                <h3>{{ user.name }}</h3>
                <small>Telegram ID: {{ user.user_id }}</small>
            </div>
            <div class="balance-box">
                <small>Available Balance</small>
                <div style="font-size: 34px; font-weight: bold;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            <button class="btn btn-work" onclick="startWork()">WATCH ADS</button>
            <button class="btn btn-withdraw" onclick="openW()">WITHDRAW</button>
            <div class="info">
                👥 Total Refers: {{ user.ref_count }}<br>
                💰 Limit: ৳{{ config.min_withdraw }} - ৳{{ config.max_withdraw }}
            </div>
            <div class="ref-link">🔗 {{ ref_url }}</div>
        </div>
    </div>
    <script>
    function startWork() {
        let zid = "{{ config.zone_id }}";
        if(typeof window['show_'+zid] === 'function') {
            for(let i=0; i< {{config.ad_count}}; i++){ window['show_'+zid](); }
            fetch('/update_balance', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:"{{user.user_id}}"})})
            .then(res=>res.json()).then(data=> { if(data.success) document.getElementById('bal').innerText = data.new_balance.toFixed(2); });
        } else { alert("AdBlocker detected!"); }
    }
    function openW() {
        let amt = prompt("Amount (৳):");
        let acc = prompt("Wallet Number:");
        if(amt && acc) {
            fetch('/request_withdraw', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:"{{user.user_id}}", amount:parseFloat(amt), account:acc})})
            .then(res=>res.json()).then(data=>alert(data.message));
        }
    }
    </script>
</body>
</html>
"""

# --- Flask Routes ---
@app.route('/')
def home():
    user_id, name, ref_by = request.args.get('id'), request.args.get('name', 'User'), request.args.get('ref')
    if not user_id: return "<h1>Access via Bot Only!</h1>"
    
    config = get_settings()
    ip = get_user_ip()
    
    if config['vpn_on']:
        ip_info = check_vpn_status(ip)
        allowed = [c.strip() for c in config['allowed_countries'].split(',')]
        if ip_info['country'] not in allowed:
            return f"<body style='background:#0f172a;color:white;text-align:center;padding:50px;'><h1>VPN Error! ❌</h1><p>Allowed: {config['allowed_countries']}</p></body>"

    if not config.get('app_url'):
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": request.host_url}})

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        ip_exists = users_collection.find_one({"ip_address": ip})
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, "referred_by": ref_by, "created_at": datetime.now()}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != user_id and not ip_exists:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data

    bot_username = bot.get_me().username if bot else "Bot"
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    return render_template_string(USER_DASHBOARD, user=user, config=config, ref_url=ref_link)

@app.route('/update_balance', methods=['POST'])
def update_balance():
    data = request.json
    config = get_settings()
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": config['ad_rate']}})
    u = users_collection.find_one({"user_id": data['user_id']})
    return jsonify({"success": True, "new_balance": u['balance']})

@app.route('/request_withdraw', methods=['POST'])
def request_withdraw():
    data = request.json
    config = get_settings()
    user = users_collection.find_one({"user_id": data['user_id']})
    if data['amount'] < config['min_withdraw'] or data['amount'] > config['max_withdraw'] or user['balance'] < data['amount']:
        return jsonify({"success": False, "message": "Invalid Balance or Limit!"})
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Request Submitted!"})

# --- Admin Panel ---
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
        return '<form method="post" style="padding:100px;text-align:center;">Admin Pass: <input name="pass" type="password"><button>Login</button></form>'
    
    users = list(users_collection.find().limit(50))
    pending = list(withdraws_collection.find({"status": "Pending"}))
    return render_template_string("""
    <div style="font-family:sans-serif; padding:20px; background:#f1f5f9;">
        <h2>Admin Master Panel</h2>
        <form method="post" style="background:white; padding:20px; border-radius:10px;">
            Notice: <input name="notice" value="{{config.notice}}" style="width:100%"><br><br>
            Ad Rate: <input name="ad_rate" value="{{config.ad_rate}}"> Ad Count: <input name="ad_count" value="{{config.ad_count}}"><br><br>
            Ref Bonus: <input name="ref_commission" value="{{config.ref_commission}}"> Zone ID: <input name="zone_id" value="{{config.zone_id}}"><br><br>
            VPN: <input type="checkbox" name="vpn_on" {% if config.vpn_on %}checked{% endif %}> ON | Countries: <input name="allowed_countries" value="{{config.allowed_countries}}"><br><br>
            Min W: <input name="min_withdraw" value="{{config.min_withdraw}}"> Max W: <input name="max_withdraw" value="{{config.max_withdraw}}"><br><br>
            <button type="submit">Update Settings</button>
        </form>
        <h3>User Management</h3>
        <table border="1" width="100%" style="background:white;">
            <tr><th>Name</th><th>Balance</th><th>Action</th></tr>
            {% for u in users %}
            <tr>
                <form action="/admin/edit_user/{{u.user_id}}" method="post">
                <td><input name="name" value="{{u.name}}"></td>
                <td><input name="balance" value="{{u.balance}}"></td>
                <td><button type="submit">Save</button></td>
                </form>
            </tr>
            {% endfor %}
        </table>
        <h3>Withdraw Requests</h3>
        {% for w in pending %}
        <p>{{w.name}} (৳{{w.amount}}) - {{w.account}} <a href="/admin/pay/{{w._id}}"><button>Mark Paid</button></a></p>
        {% endfor %}
    </div>
    """, config=config, users=users, pending=pending)

@app.route('/admin/edit_user/<uid>', methods=['POST'])
def edit_user(uid):
    if session.get('logged'):
        users_collection.update_one({"user_id": uid}, {"$set": {"name": request.form.get('name'), "balance": float(request.form.get('balance'))}})
    return redirect(url_for('admin'))

@app.route('/admin/pay/<wid>')
def pay_withdraw(wid):
    if session.get('logged'): withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('logged', None); return redirect(url_for('admin'))

if __name__ == "__main__":
    if bot: threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

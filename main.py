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
ADMIN_PASSWORD_ENV = os.environ.get("ADMIN_PASS", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "MASTER_FINAL_FIX_2025")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Telegram Bot Initialization
bot = None
if BOT_TOKEN:
    try:
        bot = telebot.TeleBot(BOT_TOKEN)
        bot_user = bot.get_me()
        BOT_USERNAME = bot_user.username
        print(f"✅ Bot @{BOT_USERNAME} Started!")
    except Exception as e:
        print(f"❌ Bot Error: {e}")
        bot = None
        BOT_USERNAME = "Bot"

# --- Database Connection ---
try:
    client = MongoClient(MONGO_URI)
    db = client['mega_earning_v11']
    users_collection = db['users']
    settings_collection = db['settings']
    withdraws_collection = db['withdrawals']
    print("✅ Database Connected!")
except Exception as e:
    print(f"❌ Database Error: {e}")

# সেটিংস লোড বা ডিফল্ট তৈরি (Error Proof)
def get_settings():
    setts = settings_collection.find_one({"id": "config"})
    if not setts:
        default = {
            "id": "config", "ad_count": 1, "ad_rate": 0.50, "ref_commission": 2.00,
            "min_withdraw": 10.00, "max_withdraw": 1000.00, "withdraw_methods": "Bkash, Nagad, Rocket",
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

# --- TELEGRAM BOT LOGIC ---
if bot:
    @bot.message_handler(commands=['start'])
    def start_cmd(message):
        uid = str(message.from_user.id)
        name = message.from_user.first_name
        config = get_settings()
        ref_by = message.text.split()[1] if len(message.text.split()) > 1 else None
        
        # অটোমেটিক ইউআরএল ডিটেকশন (যদি এডমিন সেট না করে)
        base_url = config.get('app_url') if config.get('app_url') else "https://" + request.host
        dashboard_url = f"{base_url.rstrip('/')}/?id={uid}&name={name}"
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
        .card { background: #1e293b; border-radius: 20px; padding: 20px; box-shadow: 0 10px 20px rgba(0,0,0,0.4); }
        .balance { background: #10b981; padding: 20px; border-radius: 15px; margin: 15px 0; font-size: 28px; font-weight: bold; }
        .btn { width: 100%; padding: 15px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 10px; color: white; }
    </style>
</head>
<body>
    <div class="notice">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <h3>{{ user.name }}</h3>
            <div class="balance">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            <button class="btn" style="background:#3b82f6;" onclick="startWork()">WATCH ADS</button>
            <button class="btn" style="background:#f59e0b;" onclick="openW()">WITHDRAW</button>
            <p style="font-size:12px; color:#94a3b8;">Refers: {{ user.ref_count }} | ID: {{ user.user_id }}</p>
            <p style="font-size:10px; color:#64748b;">Ref Link: t.me/{{ bot_username }}?start={{ user.user_id }}</p>
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

# --- ADMIN PANEL ---
ADMIN_PANEL = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: white; padding: 20px; }
        .card { background: #1e293b; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        input, textarea, select { width: 100%; padding: 10px; margin: 5px 0; border-radius: 5px; border: 1px solid #334155; background: #0f172a; color: white; }
        button { background: #10b981; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; border-bottom: 1px solid #334155; text-align: left; font-size: 14px; }
    </style>
</head>
<body>
    <h1>💎 Admin Control Panel</h1>
    <div class="card">
        <h3>Settings</h3>
        <form method="post">
            Notice: <textarea name="notice">{{config.notice}}</textarea>
            App URL: <input name="app_url" value="{{config.app_url}}" placeholder="https://your-app.onrender.com">
            Ad Rate: <input name="ad_rate" step="0.01" value="{{config.ad_rate}}">
            Ad Count: <input name="ad_count" type="number" value="{{config.ad_count}}">
            Ref Bonus: <input name="ref_commission" step="0.01" value="{{config.ref_commission}}">
            Min Withdraw: <input name="min_withdraw" value="{{config.min_withdraw}}">
            Zone ID: <input name="zone_id" value="{{config.zone_id}}">
            VPN (on/off): <input name="vpn_on" value="{% if config.vpn_on %}on{% else %}off{% endif %}">
            <button type="submit">Update Everything</button>
        </form>
    </div>

    <div class="card">
        <h3>User Management</h3>
        <table>
            {% for u in users %}
            <tr>
                <form action="/admin/edit_user/{{u.user_id}}" method="post">
                <td>{{u.name}}<br><small>{{u.user_id}}</small></td>
                <td><input name="balance" value="{{u.balance}}" style="width:70px;"></td>
                <td><button type="submit">Save</button></td>
                </form>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="card">
        <h3>Withdrawals</h3>
        {% for w in withdraws %}
        <p>{{w.name}} - ৳{{w.amount}} ({{w.account}}) <a href="/admin/pay/{{w._id}}" style="color:red;">Mark Paid</a></p>
        {% endfor %}
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
        return f"<h1>Join via Bot first!</h1><p>Bot Link: t.me/{BOT_USERNAME}</p>", 403
    
    config = get_settings()
    ip = get_user_ip()
    
    # ইউআরএল অটো-আপডেট ফিক্স
    if not config.get('app_url'):
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": request.host_url.rstrip('/')}})

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        ip_exists = users_collection.find_one({"ip_address": ip})
        user_data = {"user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, "ip_address": ip, "referred_by": ref_by, "created_at": datetime.now()}
        users_collection.insert_one(user_data)
        if ref_by and ref_by != user_id and not ip_exists:
            users_collection.update_one({"user_id": ref_by}, {"$inc": {"balance": config['ref_commission'], "ref_count": 1}})
        user = user_data
    
    return render_template_string(USER_DASHBOARD, user=user, config=config, bot_username=BOT_USERNAME)

@app.route('/update_balance', methods=['POST'])
def update_balance():
    data = request.json
    uid = data.get('user_id')
    if uid:
        config = get_settings()
        users_collection.update_one({"user_id": uid}, {"$inc": {"balance": config['ad_rate']}})
        u = users_collection.find_one({"user_id": uid})
        return jsonify({"success": True, "new_balance": u['balance']})
    return jsonify({"success": False})

@app.route('/request_withdraw', methods=['POST'])
def request_withdraw():
    data = request.json
    config = get_settings()
    user = users_collection.find_one({"user_id": data['user_id']})
    if data['amount'] < config['min_withdraw'] or user['balance'] < data['amount']:
        return jsonify({"success": False, "message": "Invalid Balance!"})
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Requested!"})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if session.get('logged'):
            try:
                # Internal Server Error ঠেকাতে try-except এবং Default values
                settings_collection.update_one({"id": "config"}, {"$set": {
                    "notice": request.form.get('notice', config['notice']),
                    "app_url": request.form.get('app_url', config['app_url']).rstrip('/'),
                    "ad_rate": float(request.form.get('ad_rate', 0.50)),
                    "ad_count": int(request.form.get('ad_count', 1)),
                    "ref_commission": float(request.form.get('ref_commission', 2.00)),
                    "min_withdraw": float(request.form.get('min_withdraw', 10.00)),
                    "zone_id": request.form.get('zone_id', config['zone_id']),
                    "vpn_on": True if request.form.get('vpn_on') == 'on' else False
                }})
                return redirect(url_for('admin'))
            except Exception as e:
                return f"Error: {e}. Please enter numbers correctly."
        elif request.form.get('pass') == ADMIN_PASSWORD_ENV:
            session['logged'] = True
            return redirect(url_for('admin'))
    
    if not session.get('logged'):
        return '<form method="post" style="padding:100px;text-align:center;">Pass: <input name="pass" type="password"><button>Login</button></form>'
    
    users = list(users_collection.find().limit(50))
    withdraws = list(withdraws_collection.find({"status": "Pending"}))
    return render_template_string(ADMIN_PANEL, config=config, users=users, withdraws=withdraws)

@app.route('/admin/edit_user/<uid>', methods=['POST'])
def edit_user(uid):
    if session.get('logged'):
        try:
            users_collection.update_one({"user_id": uid}, {"$set": {"balance": float(request.form.get('balance', 0))}})
        except: pass
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

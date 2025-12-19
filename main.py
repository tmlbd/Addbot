import os
import threading
import time
import requests
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

app = Flask(__name__)
# SECRET_KEY কোডের ভেতরেই দিয়ে দেওয়া হলো
app.secret_key = "ULTIMATE_EARN_PRO_VERSION_FINAL_2025"

# --- MongoDB Configuration ---
# এখানে আপনার নিজের MongoDB Connection URI বসান
MONGO_URI = "আপনার_মোঙ্গোডিবি_লিঙ্ক_এখানে_দিন" 

try:
    client = MongoClient(MONGO_URI)
    db = client['earning_v9_final_db']
    users_collection = db['users']
    settings_collection = db['settings']
    withdraws_collection = db['withdrawals']
    print("Database Connected Successfully!")
except Exception as e:
    print(f"Database Connection Error: {e}")

# সেটিংস লোড বা ডিফল্ট তৈরি
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
            "notice": "সঠিক ভিপিএন কানেক্ট করে কাজ শুরু করুন।",
            "admin_pass": "admin123", 
            "zone_id": "10341337",
            "vpn_on": False,
            "allowed_countries": "US,GB,CA",
            "app_url": "" 
        }
        settings_collection.insert_one(default)
        return default
    return setts

# আইপি ও ভিপিএন চেক করার ফাংশন
def check_vpn_status(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,countryCode,proxy,hosting", timeout=5).json()
        if response.get('status') == 'success':
            return {
                "country": response.get('countryCode'),
                "is_vpn": response.get('proxy') or response.get('hosting')
            }
    except: pass
    return {"country": "Unknown", "is_vpn": False}

def get_user_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

# সাইট সজাগ রাখার সিস্টেম
def keep_alive():
    while True:
        try:
            config = get_settings()
            if config.get('app_url'):
                requests.get(config.get('app_url'), timeout=10)
        except: pass
        time.sleep(600)

# --- HTML Templates ---

# ১. ভিপিএন এরর পেজ
VPN_ERROR_PAGE = """
<body style="background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:100px;">
    <div style="background:#1e293b; display:inline-block; padding:30px; border-radius:15px; border:2px solid #ef4444;">
        <h1 style="color:#ef4444;">VPN Required! ❌</h1>
        <p>{{ message }}</p>
        <p>Allowed: <b>{{ countries }}</b></p>
        <button onclick="location.reload()" style="padding:10px 20px; background:#3b82f6; color:white; border:none; border-radius:5px; cursor:pointer;">Refresh</button>
    </div>
</body>
"""

# ২. মেইন ড্যাশবোর্ড
USER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn Pro | Dashboard</title>
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <style>
        body { font-family: 'Poppins', sans-serif; background: #0f172a; color: white; margin: 0; }
        .notice { background: #f59e0b; color: #000; padding: 12px; font-size: 13px; font-weight: bold; text-align: center; border-bottom: 2px solid white; }
        .container { max-width: 450px; margin: 0 auto; padding: 15px; }
        .card { background: #1e293b; border-radius: 20px; padding: 25px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.4); }
        .balance-box { background: linear-gradient(135deg, #10b981, #059669); border-radius: 15px; padding: 20px; margin: 15px 0; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-bottom: 12px; }
        .btn-work { background: #3b82f6; color: white; }
        .btn-withdraw { background: #f59e0b; color: white; }
        .ref-link { background: #020617; padding: 10px; border-radius: 8px; margin-top: 20px; font-size: 11px; word-break: break-all; color: #60a5fa; }
    </style>
</head>
<body>
    <div class="notice">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=3b82f6&color=fff" style="width:75px; border-radius:50%;">
            <h3>{{ user.name }}</h3>
            <div class="balance-box">
                <small>Current Balance</small>
                <div style="font-size: 34px; font-weight: bold;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            <button class="btn btn-work" onclick="startWork()">WATCH ADS</button>
            <button class="btn btn-withdraw" onclick="openW()">WITHDRAW</button>
            <div style="font-size: 12px; color: #94a3b8; text-align: left; margin-top:15px;">
                ID: {{ user.user_id }} | Refers: {{ user.ref_count }}<br>
                Limit: ৳{{ config.min_withdraw }} - ৳{{ config.max_withdraw }}
            </div>
            <div class="ref-link">{{ ref_url }}</div>
        </div>
    </div>
    <script>
    function startWork() {
        let zid = "{{ config.zone_id }}";
        if (typeof window['show_' + zid] === 'function') {
            for (let i = 0; i < {{ config.ad_count }}; i++) { window['show_' + zid](); }
            fetch('/update_balance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: "{{ user.user_id }}" })
            }).then(res => res.json()).then(data => {
                if(data.success) document.getElementById('bal').innerText = data.new_balance.toFixed(2);
            });
        } else { alert("AdBlocker detected! Please disable it."); }
    }
    function openW() { 
        let amt = prompt("টাকার পরিমাণ লিখুন:");
        let acc = prompt("বিকাশ/নগদ নাম্বার লিখুন:");
        if(amt && acc) {
            fetch('/request_withdraw', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: "{{ user.user_id }}", amount: parseFloat(amt), account: acc })
            }).then(res => res.json()).then(data => alert(data.message));
        }
    }
    </script>
</body>
</html>
"""

# --- Routes ---

@app.route('/')
def home():
    user_id, name, ref_by = request.args.get('id'), request.args.get('name', 'User'), request.args.get('ref')
    if not user_id: return "Access via Bot only!"
    
    config = get_settings()
    ip = get_user_ip()
    ip_info = check_vpn_status(ip)
    
    # VPN চেক (যদি এডমিন থেকে অন থাকে)
    if config['vpn_on']:
        allowed = [c.strip() for c in config['allowed_countries'].split(',')]
        if ip_info['country'] not in allowed:
            return render_template_string(VPN_ERROR_PAGE, message="সঠিক দেশের ভিপিএন কানেক্ট করুন!", countries=config['allowed_countries'])

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

    ref_link = f"{request.host_url}?id={user_id}&name={name}&ref={user_id}"
    return render_template_string(USER_DASHBOARD, user=user, config=config, ref_url=ref_link)

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
        return jsonify({"success": False, "message": "Invalid Balance or Limit!"})
    
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({"user_id": data['user_id'], "name": user['name'], "amount": data['amount'], "account": data['account'], "status": "Pending", "date": datetime.now()})
    return jsonify({"success": True, "message": "Withdraw Request Sent Successfully!"})

# --- Admin Panel ---

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if session.get('logged'):
            # সেটিংস ও ভিপিএন আপডেট
            vpn_status = True if request.form.get('vpn_on') == 'on' else False
            settings_collection.update_one({"id": "config"}, {"$set": {
                "ad_rate": float(request.form.get('ad_rate')), 
                "ref_commission": float(request.form.get('ref_commission')),
                "min_withdraw": float(request.form.get('min_withdraw')), 
                "max_withdraw": float(request.form.get('max_withdraw')),
                "notice": request.form.get('notice'), 
                "ad_count": int(request.form.get('ad_count')),
                "zone_id": request.form.get('zone_id'),
                "vpn_on": vpn_status,
                "allowed_countries": request.form.get('allowed_countries')
            }})
            return redirect(url_for('admin'))
        elif request.form.get('pass') == config['admin_pass']:
            session['logged'] = True
            return redirect(url_for('admin'))

    if not session.get('logged'):
        return '<div style="text-align:center; padding:100px;"><h2>Admin Login</h2><form method="post"><input name="pass" type="password"><button>Login</button></form></div>'
    
    all_users = list(users_collection.find().limit(50))
    pending_withdraws = list(withdraws_collection.find({"status": "Pending"}))
    
    return render_template_string("""
    <div style="padding:20px; font-family:sans-serif; background:#f4f7f6; max-width:1100px; margin:0 auto; border-radius:15px;">
        <h2>Admin Master Dashboard</h2>
        
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:white; padding:20px; border-radius:10px; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
                <h3>System Config</h3>
                <form method="post">
                    Notice: <input name="notice" value="{{config.notice}}" style="width:100%;"><br><br>
                    Ad Rate: <input name="ad_rate" value="{{config.ad_rate}}"> Ad Count: <input name="ad_count" value="{{config.ad_count}}"><br><br>
                    Ref Bonus: <input name="ref_commission" value="{{config.ref_commission}}"> Zone ID: <input name="zone_id" value="{{config.zone_id}}"><br><br>
                    Min W: <input name="min_withdraw" value="{{config.min_withdraw}}"> Max W: <input name="max_withdraw" value="{{config.max_withdraw}}"><br><br>
                    <b>VPN Security:</b><br>
                    VPN ON: <input type="checkbox" name="vpn_on" {% if config.vpn_on %}checked{% endif %}> | Countries: <input name="allowed_countries" value="{{config.allowed_countries}}"><br><br>
                    <button type="submit" style="background:green; color:white; padding:10px 20px; border:none; cursor:pointer; width:100%;">Save Settings</button>
                </form>
            </div>

            <div style="background:white; padding:20px; border-radius:10px; box-shadow:0 2px 5px rgba(0,0,0,0.1);">
                <h3>Withdraw Requests</h3>
                <table border="1" width="100%" style="border-collapse:collapse;">
                    <tr><th>Name</th><th>Amount</th><th>Number</th><th>Action</th></tr>
                    {% for w in withdraws %}
                    <tr><td>{{w.name}}</td><td>{{w.amount}}</td><td>{{w.account}}</td><td><a href="/admin/pay/{{w._id}}">Mark Paid</a></td></tr>
                    {% endfor %}
                </table>
            </div>
        </div>

        <div style="background:white; padding:20px; border-radius:10px; margin-top:20px;">
            <h3>User Management (Edit Balance/Data)</h3>
            <table border="1" width="100%" style="border-collapse:collapse;">
                <tr style="background:#eee;"><th>Name</th><th>Balance</th><th>Refers</th><th>Action</th></tr>
                {% for u in users %}
                <tr>
                    <form action="/admin/edit_user/{{u.user_id}}" method="post">
                    <td><input name="name" value="{{u.name}}" style="width:100px;"></td>
                    <td><input name="balance" value="{{u.balance}}" style="width:80px;"></td>
                    <td><input name="ref_count" value="{{u.ref_count}}" style="width:50px;"></td>
                    <td><button type="submit" style="background:#3b82f6; color:white; border:none; padding:5px; cursor:pointer;">Update</button></td>
                    </form>
                </tr>
                {% endfor %}
            </table>
        </div>
        <br><a href="/logout" style="color:red; text-decoration:none;">Logout Admin</a>
    </div>
    """, config=config, users=all_users, withdraws=pending_withdraws)

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
    if session.get('logged'): withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('logged', None); return redirect(url_for('admin'))

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

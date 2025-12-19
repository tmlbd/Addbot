import os
import threading
import time
import requests
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "final_secure_earning_v8_2025"

# --- MongoDB Configuration ---
# আপনার MongoDB Connection String এখানে দিন
MONGO_URI = "your_mongodb_connection_string_here" 
client = MongoClient(MONGO_URI)
db = client['ad_earning_final_db']
users_collection = db['users']
settings_collection = db['settings']
withdraws_collection = db['withdrawals']

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
            "notice": "স্বাগতম! কাজ শুরু করতে WATCH ADS বাটনে ক্লিক করুন।",
            "admin_pass": "admin123", 
            "zone_id": "10341337",
            "app_url": "" # রেন্ডার ইউআরএল এখানে অটো সেভ হবে
        }
        settings_collection.insert_one(default)
        return default
    return setts

def get_user_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]

# --- ১. সাইট সজাগ রাখার সিস্টেম (Self-Ping Logic) ---
def keep_alive():
    while True:
        try:
            config = get_settings()
            url = config.get('app_url')
            if url:
                requests.get(url)
                print(f"[{datetime.now()}] Ping sent to {url} - Status: Active")
        except Exception as e:
            print(f"Ping Error: {e}")
        time.sleep(600) # প্রতি ১০ মিনিট (৬০০ সেকেন্ড) পর পর পিং করবে

# --- HTML Template ---
USER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn Pro | Dashboard</title>
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <style>
        body { font-family: 'Poppins', sans-serif; background: #0f172a; color: white; margin: 0; padding: 0; }
        .notice-bar { background: #f59e0b; color: #000; padding: 10px; font-size: 13px; font-weight: bold; text-align: center; }
        .container { max-width: 480px; margin: 0 auto; padding: 15px; }
        .card { background: #1e293b; border-radius: 20px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); text-align: center; }
        .balance-card { background: linear-gradient(135deg, #3b82f6, #2563eb); border-radius: 15px; padding: 20px; margin: 15px 0; }
        .btn-work { background: #10b981; color: white; border: none; width: 100%; padding: 15px; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-bottom: 10px; }
        .btn-withdraw { background: #f59e0b; color: white; border: none; width: 100%; padding: 15px; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; }
        .ref-box { background: #020617; padding: 12px; border-radius: 10px; margin-top: 15px; font-size: 11px; text-align: left; word-break: break-all; color: #94a3b8; }
        
        #withdrawModal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; }
        .modal-content { background: #1e293b; margin: 10% auto; padding: 20px; width: 85%; max-width: 380px; border-radius: 15px; }
        input, select { width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px; border: none; background: #334155; color: white; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="notice-bar">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=3b82f6&color=fff" style="width:70px; border-radius:50%; border:3px solid #3b82f6;">
            <h3>{{ user.name }}</h3>
            <p style="font-size:12px; color:#94a3b8; margin-top:-10px;">ID: {{ user.user_id }}</p>
            
            <div class="balance-card">
                <small>Current Balance</small>
                <div style="font-size: 32px; font-weight: bold;">৳ <span id="balance_val">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>

            <button class="btn-work" onclick="startWork()">WATCH ADS & EARN</button>
            <button class="btn-withdraw" onclick="openWithdraw()">WITHDRAW</button>

            <div style="margin-top: 20px; text-align: left; font-size: 13px;">
                <p>👥 Total Refers: {{ user.ref_count }}</p>
                <p>💰 Limit: ৳{{ config.min_withdraw }} - ৳{{ config.max_withdraw }}</p>
            </div>
            <div class="ref-box">🔗 Ref Link: {{ ref_url }}</div>
        </div>
    </div>

    <!-- Withdrawal Modal -->
    <div id="withdrawModal">
        <div class="modal-content">
            <h3 style="margin-top:0;">Request Money</h3>
            <select id="w_method">
                {% for m in config.withdraw_methods %} <option value="{{ m }}">{{ m }}</option> {% endfor %}
            </select>
            <input type="number" id="w_amount" placeholder="Amount (৳)">
            <input type="text" id="w_account" placeholder="Wallet Number">
            <button onclick="submitWithdraw()" style="background:#10b981; color:white; width:100%; padding:12px; border:none; border-radius:8px; font-weight:bold;">Submit</button>
            <button onclick="closeWithdraw()" style="background:none; color:#94a3b8; width:100%; border:none; margin-top:10px;">Cancel</button>
        </div>
    </div>

    <script>
    function startWork() {
        let zone = "{{ config.zone_id }}";
        if (typeof window['show_' + zone] === 'function') {
            for (let i = 0; i < {{ config.ad_count }}; i++) { window['show_' + zone](); }
            updateBalance();
        } else { alert("Disable AdBlocker!"); }
    }
    function updateBalance() {
        fetch('/update_balance', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: "{{ user.user_id }}" })
        }).then(res => res.json()).then(data => {
            if(data.success) document.getElementById('balance_val').innerText = data.new_balance.toFixed(2);
        });
    }
    function openWithdraw() { document.getElementById('withdrawModal').style.display = 'block'; }
    function closeWithdraw() { document.getElementById('withdrawModal').style.display = 'none'; }
    function submitWithdraw() {
        let amt = parseFloat(document.getElementById('w_amount').value);
        if(amt < {{ config.min_withdraw }} || amt > {{ config.max_withdraw }}) return alert("Out of Limit!");
        fetch('/request_withdraw', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: "{{ user.user_id }}", method: document.getElementById('w_method').value, amount: amt, account: document.getElementById('w_account').value })
        }).then(res => res.json()).then(data => { alert(data.message); if(data.success) location.reload(); });
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
    # প্রথমবার ঢুকলে অ্যাপ ইউআরএল সেভ করা (সজাগ রাখার জন্য)
    if not config.get('app_url'):
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": request.host_url}})

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        ip = get_user_ip()
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
        return jsonify({"success": False, "message": "Invalid Request!"})
    
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({
        "user_id": data['user_id'], "name": user['name'], "amount": data['amount'], 
        "method": data['method'], "account": data['account'], "status": "Pending", "date": datetime.now()
    })
    return jsonify({"success": True, "message": "Withdrawal request sent!"})

# --- Admin Panel ---

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if session.get('logged'):
            methods = [m.strip() for m in request.form.get('methods').split(',')]
            settings_collection.update_one({"id": "config"}, {"$set": {
                "ad_rate": float(request.form.get('ad_rate')), "ref_commission": float(request.form.get('ref_commission')),
                "min_withdraw": float(request.form.get('min_withdraw')), "max_withdraw": float(request.form.get('max_withdraw')),
                "withdraw_methods": methods, "notice": request.form.get('notice'), "ad_count": int(request.form.get('ad_count'))
            }})
            return redirect(url_for('admin'))
        elif request.form.get('pass') == config['admin_pass']:
            session['logged'] = True
            return redirect(url_for('admin'))

    if not session.get('logged'):
        return '<form method="post" style="padding:100px;text-align:center;">Pass: <input name="pass" type="password"><button>Login</button></form>'
    
    pending = list(withdraws_collection.find({"status": "Pending"}))
    return render_template_string("""
    <div style="padding:20px; font-family:sans-serif; background:#f1f5f9;">
        <h2>Settings</h2>
        <form method="post">
            Notice: <textarea name="notice" style="width:100%">{{config.notice}}</textarea><br>
            Ad Rate: <input name="ad_rate" value="{{config.ad_rate}}"> | Ads/Click: <input name="ad_count" value="{{config.ad_count}}"><br>
            Min: <input name="min_withdraw" value="{{config.min_withdraw}}"> | Max: <input name="max_withdraw" value="{{config.max_withdraw}}"><br>
            Methods: <input name="methods" value="{{config.withdraw_methods|join(', ')}}" style="width:100%"><br><br>
            <button type="submit">Update Everything</button>
        </form>
        <h3>Pending Withdrawals</h3>
        <table border="1" width="100%">
            <tr><th>Name</th><th>Amount</th><th>Method</th><th>Account</th><th>Action</th></tr>
            {% for w in withdraws %}
            <tr>
                <td>{{w.name}}</td><td>{{w.amount}}</td><td>{{w.method}}</td><td>{{w.account}}</td>
                <td><a href="/admin/pay/{{w._id}}"><button>Mark Paid</button></a></td>
            </tr>
            {% endfor %}
        </table>
        <br><a href="/logout">Logout</a>
    </div>
    """, config=config, withdraws=pending)

@app.route('/admin/pay/<wid>')
def pay_withdraw(wid):
    if session.get('logged'):
        withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('logged', None); return redirect(url_for('admin'))

if __name__ == "__main__":
    # সজাগ রাখার থ্রেড চালু করা
    threading.Thread(target=keep_alive, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

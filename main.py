import os
import threading
import time
import requests
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

app = Flask(__name__)
# এটি আপনার সেশন সিকিউরিটির জন্য
app.secret_key = "ULTIMATE_ALL_IN_ONE_EARN_APP_2025"

# --- MongoDB Configuration ---
# এখানে আপনার নিজের MongoDB Connection URI টি অবশ্যই বসাবেন
MONGO_URI = "mongodb+srv://roxiw19528:roxiw19528@cluster0.vl508y4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" 

try:
    client = MongoClient(MONGO_URI)
    db = client['final_master_earning_db']
    users_collection = db['users']
    settings_collection = db['settings']
    withdraws_collection = db['withdrawals']
    print("Database Connected Successfully!")
except Exception as e:
    print(f"Database Connection Error: {e}")

# সেটিংস লোড বা ডিফল্ট তৈরি করা
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
            "notice": "সঠিক ভিপিএন কানেক্ট করে কাজ শুরু করুন এবং বেশি বেশি রেফার করুন।",
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
        # ip-api.com ব্যবহার করে আইপি ইনফো চেক করা
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

# সাইট সজাগ রাখার সিস্টেম (Keep-Alive)
def keep_alive():
    while True:
        try:
            config = get_settings()
            if config.get('app_url'):
                requests.get(config.get('app_url'), timeout=10)
        except: pass
        time.sleep(600) # ১০ মিনিট পরপর পিং করবে

# --- HTML Templates ---

# ১. ভিপিএন ওয়ার্নিং পেজ
VPN_ERROR_PAGE = """
<body style="background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:100px;">
    <div style="background:#1e293b; display:inline-block; padding:30px; border-radius:15px; border:2px solid #f59e0b;">
        <h1 style="color:#f59e0b;">VPN Requirement! ⚠️</h1>
        <p>{{ message }}</p>
        <p>অনুমোদিত দেশ: <b>{{ countries }}</b></p>
        <button onclick="location.reload()" style="padding:12px 25px; background:#3b82f6; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">Refresh Page</button>
    </div>
</body>
"""

# ২. ইউজার ড্যাশবোর্ড (মোবাইল ফ্রেন্ডলি ডার্ক থিম)
USER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earn Panel | Dashboard</title>
    <!-- Monetag SDK Dynamic Zone ID -->
    <script src='//libtl.com/sdk.js' data-zone='{{ config.zone_id }}' data-sdk='show_{{ config.zone_id }}'></script>
    <style>
        body { font-family: 'Poppins', sans-serif; background: #0f172a; color: white; margin: 0; }
        .notice-bar { background: linear-gradient(90deg, #f59e0b, #d97706); color: #000; padding: 12px; font-size: 13px; font-weight: bold; text-align: center; border-bottom: 2px solid white; }
        .container { max-width: 480px; margin: 0 auto; padding: 15px; }
        .card { background: #1e293b; border-radius: 20px; padding: 25px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.4); }
        .profile-img { width: 80px; height: 80px; border-radius: 50%; border: 3px solid #3b82f6; margin-bottom: 10px; }
        .balance-card { background: linear-gradient(135deg, #10b981, #059669); border-radius: 15px; padding: 20px; margin: 15px 0; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-bottom: 12px; transition: 0.3s; }
        .btn-work { background: #3b82f6; color: white; }
        .btn-withdraw { background: #f59e0b; color: white; }
        .btn:active { transform: scale(0.98); }
        .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 20px; text-align: left; }
        .stat-item { background: #334155; padding: 10px; border-radius: 10px; font-size: 13px; }
        .ref-link { background: #020617; padding: 12px; border-radius: 10px; margin-top: 20px; font-size: 11px; word-break: break-all; color: #60a5fa; border: 1px dashed #3b82f6; }
    </style>
</head>
<body>
    <div class="notice-bar">📢 {{ config.notice }}</div>
    <div class="container">
        <div class="card">
            <img src="https://ui-avatars.com/api/?name={{ user.name }}&background=3b82f6&color=fff&size=128" class="profile-img">
            <h2 style="margin:5px 0;">{{ user.name }}</h2>
            <div class="balance-card">
                <small>Available Balance</small>
                <div style="font-size: 34px; font-weight: bold;">৳ <span id="bal">{{ "%.2f"|format(user.balance) }}</span></div>
            </div>
            
            <button class="btn btn-work" onclick="startWork()">WATCH ADS & EARN</button>
            <button class="btn btn-withdraw" onclick="openW()">WITHDRAW</button>
            
            <div class="stats-grid">
                <div class="stat-item">🆔 ID: {{ user.user_id }}</div>
                <div class="stat-item">👥 Refers: {{ user.ref_count }}</div>
                <div class="stat-item">🚩 Min: ৳{{ config.min_withdraw }}</div>
                <div class="stat-item">🚀 Max: ৳{{ config.max_withdraw }}</div>
            </div>
            
            <div style="margin-top:20px; font-size:12px; color:#94a3b8;">Referral Link:</div>
            <div class="ref-link">{{ ref_url }}</div>
        </div>
    </div>

    <script>
    function startWork() {
        let zid = "{{ config.zone_id }}";
        if (typeof window['show_' + zid] === 'function') {
            for (let i = 0; i < {{ config.ad_count }}; i++) { window['show_' + zid](); }
            // আপডেট ব্যালেন্স সার্ভার সাইডে পাঠানো
            fetch('/update_balance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ user_id: "{{ user.user_id }}" })
            }).then(res => res.json()).then(data => {
                if(data.success) document.getElementById('bal').innerText = data.new_balance.toFixed(2);
            });
        } else { alert("AdBlocker detected! Please disable it to work."); }
    }

    function openW() { 
        let amt = prompt("টাকার পরিমাণ লিখুন (Minimum ৳{{config.min_withdraw}}):");
        let acc = prompt("বিকাশ/নগদ/রকেট নাম্বার লিখুন:");
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
    if not user_id: return "Access Denied! Use Bot Link."
    
    config = get_settings()
    ip = get_user_ip()
    
    # ১. VPN ও দেশ চেকিং (যদি এডমিন থেকে অন থাকে)
    if config['vpn_on']:
        ip_info = check_vpn_status(ip)
        allowed = [c.strip() for c in config['allowed_countries'].split(',')]
        if ip_info['country'] not in allowed:
            return render_template_string(VPN_ERROR_PAGE, message="দয়া করে অনুমোদিত দেশের ভিপিএন কানেক্ট করুন!", countries=config['allowed_countries'])

    # ২. অ্যাপ ইউআরএল অটো সেভ করা সজাগ রাখার জন্য
    if not config.get('app_url'):
        settings_collection.update_one({"id": "config"}, {"$set": {"app_url": request.host_url}})

    # ৩. ইউজার লজিক
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        # ৪. আইপি ট্র্যাকিং (একাধিক আইডি দিয়ে রেফারেল কমিশন ঠেকানো)
        ip_exists = users_collection.find_one({"ip_address": ip})
        user_data = {
            "user_id": user_id, "name": name, "balance": 0.0, "ref_count": 0, 
            "ip_address": ip, "referred_by": ref_by, "created_at": datetime.now()
        }
        users_collection.insert_one(user_data)
        
        # যদি কেউ রেফার করে থাকে এবং আইপি ইউনিক হয়
        if ref_by and ref_by != user_id and not ip_exists:
            users_collection.update_one(
                {"user_id": ref_by}, 
                {"$inc": {"balance": config['ref_commission'], "ref_count": 1}}
            )
        user = user_data

    # ইউজারের নিজস্ব রেফার লিঙ্ক
    ref_link = f"{request.host_url}?id={user_id}&name={name}&ref={user_id}"
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
    
    # ব্যালেন্স কেটে রিকোয়েস্ট পেন্ডিং রাখা
    users_collection.update_one({"user_id": data['user_id']}, {"$inc": {"balance": -data['amount']}})
    withdraws_collection.insert_one({
        "user_id": data['user_id'], "name": user['name'], "amount": data['amount'], 
        "account": data['account'], "status": "Pending", "date": datetime.now()
    })
    return jsonify({"success": True, "message": "Withdraw Request Submitted!"})

# --- Admin Panel (মাস্টার কন্ট্রোল) ---

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    config = get_settings()
    if request.method == 'POST':
        if session.get('logged'):
            # সেটিংস আপডেট
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
                "allowed_countries": request.form.get('allowed_countries'),
                "admin_pass": request.form.get('admin_pass')
            }})
            return redirect(url_for('admin'))
        elif request.form.get('pass') == config['admin_pass']:
            session['logged'] = True
            return redirect(url_for('admin'))

    if not session.get('logged'):
        return '<div style="text-align:center; padding-top:100px;"><h2>Admin Login</h2><form method="post"><input name="pass" type="password" placeholder="Password"><button>Login</button></form></div>'
    
    # ইউজার ও উইথড্র তথ্য
    all_users = list(users_collection.find().sort("created_at", -1).limit(50))
    pending_withdraws = list(withdraws_collection.find({"status": "Pending"}))
    
    return render_template_string("""
    <div style="padding:20px; font-family:sans-serif; background:#f4f7f6; max-width:1100px; margin:0 auto; border-radius:15px; color:#333;">
        <h1 style="text-align:center;">Admin Master Panel ⚙️</h1>
        
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div style="background:white; padding:20px; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                <h3>App Configurations</h3>
                <form method="post">
                    Notice: <input name="notice" value="{{config.notice}}" style="width:100%;"><br><br>
                    Ad Rate: <input name="ad_rate" value="{{config.ad_rate}}" step="0.01"> Ad Count: <input name="ad_count" value="{{config.ad_count}}"><br><br>
                    Ref Bonus: <input name="ref_commission" value="{{config.ref_commission}}" step="0.01"> <br><br>
                    Min W: <input name="min_withdraw" value="{{config.min_withdraw}}"> Max W: <input name="max_withdraw" value="{{config.max_withdraw}}"><br><br>
                    <b>Monetag Zone ID:</b> <input name="zone_id" value="{{config.zone_id}}" style="background:#e0f2fe;"><br><br>
                    <div style="background:#fff3cd; padding:10px; border-radius:5px;">
                        <b>VPN Settings:</b><br>
                        VPN Enabled: <input type="checkbox" name="vpn_on" {% if config.vpn_on %}checked{% endif %}> ON / OFF<br>
                        Allowed ISO: <input name="allowed_countries" value="{{config.allowed_countries}}" placeholder="US,GB,CA">
                    </div><br>
                    Admin Password: <input name="admin_pass" value="{{config.admin_pass}}"><br><br>
                    <button type="submit" style="background:green; color:white; padding:12px 25px; border:none; cursor:pointer; width:100%; font-weight:bold; border-radius:5px;">SAVE ALL CHANGES</button>
                </form>
            </div>

            <div style="background:white; padding:20px; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                <h3>Withdrawal Requests (Pending)</h3>
                <table border="1" width="100%" style="border-collapse:collapse; text-align:center;">
                    <tr style="background:#eee;"><th>Name</th><th>Amount</th><th>Number</th><th>Action</th></tr>
                    {% for w in withdraws %}
                    <tr>
                        <td>{{w.name}}</td><td>৳{{w.amount}}</td><td>{{w.account}}</td>
                        <td><a href="/admin/pay/{{w._id}}"><button style="background:#10b981; color:white; border:none; padding:5px; border-radius:3px; cursor:pointer;">Pay Success</button></a></td>
                    </tr>
                    {% endfor %}
                </table>
                {% if not withdraws %}<p style="text-align:center; color:grey;">No pending requests.</p>{% endif %}
            </div>
        </div>

        <div style="background:white; padding:20px; border-radius:10px; margin-top:20px; box-shadow:0 2px 10px rgba(0,0,0,0.1);">
            <h3>User Management (Balance/Ref/Info Edit)</h3>
            <div style="overflow-x:auto;">
                <table border="1" width="100%" style="border-collapse:collapse; text-align:center;">
                    <tr style="background:#334155; color:white;"><th>Name</th><th>ID</th><th>Balance (৳)</th><th>Refers</th><th>Action</th></tr>
                    {% for u in users %}
                    <tr>
                        <form action="/admin/edit_user/{{u.user_id}}" method="post">
                        <td><input name="name" value="{{u.name}}" style="width:100px;"></td>
                        <td>{{u.user_id}}</td>
                        <td><input name="balance" value="{{u.balance}}" step="0.01" style="width:80px;"></td>
                        <td><input name="ref_count" value="{{u.ref_count}}" style="width:40px;"></td>
                        <td><button type="submit" style="background:#3b82f6; color:white; border:none; padding:5px 10px; cursor:pointer; border-radius:3px;">Update</button></td>
                        </form>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
        <br><p style="text-align:center;"><a href="/logout" style="color:red; font-weight:bold; text-decoration:none;">Logout Admin Panel</a></p>
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
    if session.get('logged'):
        withdraws_collection.update_one({"_id": ObjectId(wid)}, {"$set": {"status": "Paid"}})
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.pop('logged', None); return redirect(url_for('admin'))

# --- মেইন এক্সিকিউশন ---

if __name__ == "__main__":
    # সাইট সজাগ রাখার থ্রেড চালু করা
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # রেন্ডার বা লোকাল সার্ভার পোর্ট
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

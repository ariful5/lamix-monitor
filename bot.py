import os
import json
import base64
import requests

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
GITHUB_TOKEN   = os.environ.get('MY_PAT_TOKEN', '')
GITHUB_REPO    = os.environ.get('GITHUB_REPO', 'ariful5/lamix-monitor')
ADMIN_ID       = os.environ.get('ADMIN_ID', '')
CONFIG_FILE    = 'users_config.json'
OFFSET_FILE    = 'last_update_id.txt'

GH_HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

STATUS_PENDING  = 'pending'
STATUS_APPROVED = 'approved'
STATUS_BANNED   = 'banned'
DEFAULT_LIMIT   = 1

def gh_get(filename):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    r = requests.get(url, headers=GH_HEADERS, timeout=10)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data['content']).decode()
        return content, data['sha']
    return None, None

def gh_save(filename, content_str, sha=None, msg="Update"):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    content = base64.b64encode(content_str.encode()).decode()
    body = {'message': msg, 'content': content}
    if sha:
        body['sha'] = sha
    r = requests.put(url, headers=GH_HEADERS, json=body, timeout=10)
    if r.status_code in [200, 201]:
        return r.json().get('content', {}).get('sha')
    print(f"❌ gh_save failed [{r.status_code}]: {r.text[:200]}")
    return None

def load_config():
    raw, sha = gh_get(CONFIG_FILE)
    if raw:
        return json.loads(raw), sha
    return {}, None

def save_config(config, sha=None):
    return gh_save(CONFIG_FILE,
                   json.dumps(config, indent=2, ensure_ascii=False),
                   sha, "🔧 Update user config")

def load_offset():
    raw, sha = gh_get(OFFSET_FILE)
    if raw:
        try:
            return int(raw.strip()), sha
        except:
            pass
    return 0, None

def save_offset(offset, sha=None):
    return gh_save(OFFSET_FILE, str(offset), sha, "Update offset")

def tg(method, **kwargs):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    r = requests.post(url, json=kwargs, timeout=15)
    return r.json()

def send(chat_id, text, reply_markup=None):
    params = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    tg('sendMessage', **params)

def set_bot_commands():
    tg('setMyCommands',
       commands=[
           {"command": "start",  "description": "🤖 Bot শুরু করুন"},
           {"command": "add",    "description": "➕ Keyword যোগ করুন"},
           {"command": "remove", "description": "➖ Keyword মুছুন"},
           {"command": "list",   "description": "📋 সব keyword দেখুন"},
       ],
       scope={"type": "default"})
    if ADMIN_ID:
        tg('setMyCommands',
           commands=[
               {"command": "start",    "description": "🤖 Bot শুরু করুন"},
               {"command": "add",      "description": "➕ Keyword যোগ করুন"},
               {"command": "remove",   "description": "➖ Keyword মুছুন"},
               {"command": "list",     "description": "📋 সব keyword দেখুন"},
               {"command": "users",    "description": "👥 সব user দেখুন"},
               {"command": "approve",  "description": "✅ User approve করুন"},
               {"command": "reject",   "description": "❌ User reject করুন"},
               {"command": "revoke",   "description": "🚫 Access বন্ধ করুন"},
               {"command": "notice",   "description": "📢 সবাইকে notice পাঠান"},
               {"command": "setlimit", "description": "🔢 User limit পরিবর্তন করুন"},
           ],
           scope={"type": "chat", "chat_id": int(ADMIN_ID)})
    print("✅ Bot commands set করা হয়েছে")

def notify_admin(uid, name, username):
    if not ADMIN_ID:
        return
    uname = f"@{username}" if username else "নেই"
    markup = {"inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": f"approve_{uid}"},
        {"text": "❌ Reject",  "callback_data": f"reject_{uid}"}
    ]]}
    send(ADMIN_ID,
        f"🔔 <b>নতুন Request!</b>\n\n"
        f"👤 নাম: <b>{name}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"📛 Username: {uname}\n\n"
        f"⚡ <b>Command দিয়ে এখনই:</b>\n"
        f"<code>/approve {uid}</code>\n"
        f"<code>/reject {uid}</code>\n\n"
        f"অথবা বাটন চাপুন (পরের cron-এ কাজ করবে)।",
        reply_markup=markup)

def handle_start(uid, name, username, config, sha):
    uid_str = str(uid)
    if uid_str == str(ADMIN_ID):
        if uid_str not in config:
            config[uid_str] = {
                'name': name,
                'status': STATUS_APPROVED,
                'keywords': [],
                'limit': 999
            }
            new_sha = save_config(config, sha)
            if new_sha:
                sha = new_sha
        send(uid,
            f"👑 স্বাগতম Admin <b>{name}</b>!\n\n"
            f"🛡 <b>Admin কমান্ড:</b>\n"
            f"/users — সব user দেখুন\n"
            f"/approve ID — approve করুন\n"
            f"/reject ID — reject করুন\n"
            f"/revoke ID — access বন্ধ করুন\n"
            f"/notice বার্তা — সবাইকে notice পাঠান\n"
            f"/setlimit ID সংখ্যা — limit পরিবর্তন করুন\n\n"
            f"📋 <b>নিজের কমান্ড:</b>\n"
            f"/add /remove /list")
        return config, sha

    if uid_str not in config:
        config[uid_str] = {
            'name': name,
            'status': STATUS_PENDING,
            'keywords': [],
            'limit': DEFAULT_LIMIT
        }
        new_sha = save_config(config, sha)
        if new_sha:
            sha = new_sha
            notify_admin(uid, name, username)
            send(uid,
                f"👋 হ্যালো <b>{name}</b>!\n\n"
                f"⏳ <b>Waiting for Approval...</b>\n\n"
                f"আপনার request Admin-এর কাছে পাঠানো হয়েছে।\n"
                f"Approve হলে আপনাকে জানানো হবে। 🔔")
        else:
            del config[uid_str]
            send(uid, "⚠️ সার্ভার সমস্যা। একটু পরে আবার /start দিন।")
        return config, sha

    status = config[uid_str].get('status')
    if status == STATUS_APPROVED:
        limit = config[uid_str].get('limit', DEFAULT_LIMIT)
        send(uid,
            f"👋 স্বাগতম <b>{name}</b>!\n\n"
            f"🤖 <b>Lamix Alert Bot</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>কমান্ড:</b>\n"
            f"▶ /add keyword — keyword যোগ\n"
            f"▶ /remove keyword — keyword মুছুন\n"
            f"▶ /list — সব keyword দেখুন\n\n"
            f"📊 আপনার limit: <b>{limit}</b> টা keyword")
    elif status == STATUS_PENDING:
        send(uid, "⏳ আপনার request এখনো pending। একটু অপেক্ষা করুন।")
    elif status == STATUS_BANNED:
        send(uid, "🚫 দুঃখিত, আপনার access বন্ধ করা হয়েছে।")

    return config, sha

def check_access(uid_str, config):
    if uid_str == str(ADMIN_ID):
        return True
    return config.get(uid_str, {}).get('status') == STATUS_APPROVED

def handle_add(uid, text, config, sha):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return config, sha
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send(uid, "⚠️ লিখুন: <code>/add example.com</code>")
        return config, sha
    keyword = parts[1].strip().lower()
    if uid_str not in config:
        config[uid_str] = {'name': '', 'status': STATUS_APPROVED, 'keywords': [], 'limit': DEFAULT_LIMIT}
    if keyword in config[uid_str]['keywords']:
        send(uid, f"⚠️ <b>{keyword}</b> আগে থেকেই আছে!")
        return config, sha
    is_admin = (uid_str == str(ADMIN_ID))
    limit = 999 if is_admin else config[uid_str].get('limit', DEFAULT_LIMIT)
    if len(config[uid_str]['keywords']) >= limit:
        if not is_admin:
            send(uid,
                f"❌ আপনি আর keyword যোগ করতে পারবেন না।\n\n"
                f"পুরনোটা মুছে নতুন যোগ করুন:\n"
                f"<code>/remove keyword</code>")
        return config, sha
    config[uid_str]['keywords'].append(keyword)
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        send(uid, f"✅ <b>{keyword}</b> যোগ হয়েছে!\n📊 মোট: <b>{len(config[uid_str]['keywords'])}</b> keywords")
    else:
        config[uid_str]['keywords'].remove(keyword)
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_remove(uid, text, config, sha):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return config, sha
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send(uid, "⚠️ লিখুন: <code>/remove example.com</code>")
        return config, sha
    keyword = parts[1].strip().lower()
    if keyword not in config.get(uid_str, {}).get('keywords', []):
        send(uid, f"❌ <b>{keyword}</b> আপনার list-এ নেই!")
        return config, sha
    config[uid_str]['keywords'].remove(keyword)
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        send(uid, f"🗑 <b>{keyword}</b> সরানো হয়েছে!\n📊 বাকি: <b>{len(config[uid_str]['keywords'])}</b> keywords")
    else:
        config[uid_str]['keywords'].append(keyword)
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_list(uid, config):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return
    keywords = config.get(uid_str, {}).get('keywords', [])
    limit = config.get(uid_str, {}).get('limit', DEFAULT_LIMIT)
    if not keywords:
        send(uid, "📋 কোনো keyword নেই।\n<code>/add example.com</code> দিয়ে যোগ করুন।")
        return
    lines = '\n'.join([f"  {i+1}. <code>{kw}</code>" for i, kw in enumerate(keywords)])
    send(uid, f"📋 <b>আপনার Keywords ({len(keywords)}/{limit})</b>\n\n{lines}")

def handle_users(uid, config):
    if str(uid) != str(ADMIN_ID):
        return
    approved = [(u,d) for u,d in config.items() if d.get('status')==STATUS_APPROVED]
    pending  = [(u,d) for u,d in config.items() if d.get('status')==STATUS_PENDING]
    banned   = [(u,d) for u,d in config.items() if d.get('status')==STATUS_BANNED]
    text = f"👥 <b>সব Users ({len(config)})</b>\n\n"
    if approved:
        text += f"✅ <b>Approved ({len(approved)})</b>\n"
        for u,d in approved:
            limit = d.get('limit', DEFAULT_LIMIT)
            text += f"  • {d.get('name','?')} | <code>{u}</code> | {len(d.get('keywords',[]))}/{limit} kw\n"
    if pending:
        text += f"\n⏳ <b>Pending ({len(pending)})</b>\n"
        for u,d in pending:
            text += f"  • {d.get('name','?')} | <code>{u}</code>\n"
            text += f"    👉 <code>/approve {u}</code> | <code>/reject {u}</code>\n"
    if banned:
        text += f"\n🚫 <b>Banned ({len(banned)})</b>\n"
        for u,d in banned:
            text += f"  • {d.get('name','?')} | <code>{u}</code>\n"
    send(uid, text)

def handle_notice(uid, text, config):
    if str(uid) != str(ADMIN_ID):
        return
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send(uid, "⚠️ লিখুন: <code>/notice আপনার বার্তা</code>")
        return
    notice_text = parts[1].strip()
    approved_users = [u for u,d in config.items() if d.get('status') == STATUS_APPROVED]
    success = 0
    failed = 0
    for target_uid in approved_users:
        try:
            send(int(target_uid),
                f"📢 <b>Admin Notice</b>\n\n"
                f"{notice_text}")
            success += 1
        except:
            failed += 1
    send(uid,
        f"📢 <b>Notice পাঠানো হয়েছে!</b>\n\n"
        f"✅ সফল: <b>{success}</b> জন\n"
        f"❌ ব্যর্থ: <b>{failed}</b> জন")

def handle_setlimit(uid, text, config, sha):
    if str(uid) != str(ADMIN_ID):
        return config, sha
    parts = text.split()
    if len(parts) < 3:
        send(uid, "⚠️ লিখুন: <code>/setlimit USER_ID সংখ্যা</code>")
        return config, sha
    target = parts[1].strip()
    try:
        new_limit = int(parts[2].strip())
    except:
        send(uid, "❌ সংখ্যাটা সঠিক নয়।")
        return config, sha
    if new_limit < 1:
        send(uid, "❌ limit কমপক্ষে ১ হতে হবে।")
        return config, sha
    if target not in config:
        send(uid, "❌ User পাওয়া যায়নি!")
        return config, sha
    config[target]['limit'] = new_limit
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        name = config[target].get('name', target)
        send(uid, f"✅ <b>{name}</b> এর limit <b>{new_limit}</b> করা হয়েছে!")
        send(int(target),
            f"🔔 আপনার keyword limit পরিবর্তন হয়েছে!\n\n"
            f"📊 নতুন limit: <b>{new_limit}</b> টা keyword")
    else:
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_approve_reject_revoke(uid, text, config, sha, action):
    if str(uid) != str(ADMIN_ID):
        return config, sha
    parts = text.split()
    if len(parts) < 2:
        send(uid, f"ব্যবহার: <code>/{action} USER_ID</code>")
        return config, sha
    target = parts[1].strip()
    if target not in config:
        send(uid, "❌ User পাওয়া যায়নি!")
        return config, sha
    name = config[target].get('name', target)
    if action == 'approve':
        config[target]['status'] = STATUS_APPROVED
        if 'limit' not in config[target]:
            config[target]['limit'] = DEFAULT_LIMIT
        new_sha = save_config(config, sha)
        if new_sha:
            sha = new_sha
            send(uid, f"✅ <b>{name}</b> Approved!")
            send(int(target), "🎉 <b>আপনার access Approve হয়েছে!</b>\n\nএখন bot ব্যবহার করুন:\n/add /remove /list")
        else:
            config[target]['status'] = STATUS_PENDING
            send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    elif action in ['reject', 'revoke']:
        config[target]['status'] = STATUS_BANNED
        new_sha = save_config(config, sha)
        if new_sha:
            sha = new_sha
            label = "Rejected" if action == 'reject' else "Revoked"
            send(uid, f"🚫 <b>{name}</b> {label}!")
            try:
                send(int(target), "🚫 আপনার access বন্ধ করা হয়েছে।")
            except:
                pass
        else:
            config[target]['status'] = STATUS_APPROVED
            send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_callback(callback, config, sha):
    uid  = callback['from']['id']
    data = callback.get('data', '')
    if str(uid) != str(ADMIN_ID):
        return config, sha
    if data.startswith("approve_"):
        target = data.replace("approve_", "")
        if target in config:
            config[target]['status'] = STATUS_APPROVED
            if 'limit' not in config[target]:
                config[target]['limit'] = DEFAULT_LIMIT
            new_sha = save_config(config, sha)
            if new_sha:
                sha = new_sha
                name = config[target].get('name', target)
                tg('answerCallbackQuery',
                   callback_query_id=callback['id'],
                   text=f"✅ {name} Approved!")
                tg('editMessageText',
                   chat_id=callback['message']['chat']['id'],
                   message_id=callback['message']['message_id'],
                   text=f"✅ <b>{name}</b> Approved!",
                   parse_mode='HTML')
                send(int(target), "🎉 <b>আপনার access Approve হয়েছে!</b>\n\n/add /remove /list")
            else:
                config[target]['status'] = STATUS_PENDING
                tg('answerCallbackQuery',
                   callback_query_id=callback['id'],
                   text="⚠️ Save ব্যর্থ! আবার চেষ্টা করুন।")
    elif data.startswith("reject_"):
        target = data.replace("reject_", "")
        if target in config:
            config[target]['status'] = STATUS_BANNED
            new_sha = save_config(config, sha)
            if new_sha:
                sha = new_sha
                name = config[target].get('name', target)
                tg('answerCallbackQuery',
                   callback_query_id=callback['id'],
                   text=f"🚫 {name} Rejected!")
                tg('editMessageText',
                   chat_id=callback['message']['chat']['id'],
                   message_id=callback['message']['message_id'],
                   text=f"🚫 <b>{name}</b> Rejected!",
                   parse_mode='HTML')
                try:
                    send(int(target), "🚫 আপনার request reject হয়েছে।")
                except:
                    pass
            else:
                config[target]['status'] = STATUS_PENDING
                tg('answerCallbackQuery',
                   callback_query_id=callback['id'],
                   text="⚠️ Save ব্যর্থ! আবার চেষ্টা করুন।")
    return config, sha

def main():
    print("🤖 Bot check শুরু...")
    set_bot_commands()

    offset, offset_sha = load_offset()
    config, config_sha = load_config()

    params = {'timeout': 5, 'limit': 100}
    if offset:
        params['offset'] = offset

    r = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
        params=params, timeout=15
    )
    data = r.json()

    if not data.get('ok'):
        print(f"❌ getUpdates error: {data}")
        return

    updates = data.get('result', [])
    print(f"   📨 {len(updates)} টা update পাওয়া গেছে")

    new_offset = offset
    for update in updates:
        new_offset = update['update_id'] + 1

        if 'callback_query' in update:
            config, config_sha = handle_callback(update['callback_query'], config, config_sha)
            continue

        msg = update.get('message', {})
        if not msg:
            continue

        uid   = msg['from']['id']
        name  = msg['from'].get('first_name', 'User')
        uname = msg['from'].get('username', '')
        text  = msg.get('text', '').strip()

        if not text:
            continue

        print(f"   💬 {name} ({uid}): {text}")
        cmd = text.split()[0].lower().split('@')[0]

        if cmd == '/start':
            config, config_sha = handle_start(uid, name, uname, config, config_sha)
        elif cmd == '/add':
            config, config_sha = handle_add(uid, text, config, config_sha)
        elif cmd == '/remove':
            config, config_sha = handle_remove(uid, text, config, config_sha)
        elif cmd == '/list':
            handle_list(uid, config)
        elif cmd == '/users':
            handle_users(uid, config)
        elif cmd == '/notice':
            handle_notice(uid, text, config)
        elif cmd == '/setlimit':
            config, config_sha = handle_setlimit(uid, text, config, config_sha)
        elif cmd == '/approve':
            config, config_sha = handle_approve_reject_revoke(uid, text, config, config_sha, 'approve')
        elif cmd == '/reject':
            config, config_sha = handle_approve_reject_revoke(uid, text, config, config_sha, 'reject')
        elif cmd == '/revoke':
            config, config_sha = handle_approve_reject_revoke(uid, text, config, config_sha, 'revoke')

    if new_offset != offset:
        save_offset(new_offset, offset_sha)
        print(f"   ✅ Offset updated: {new_offset}")

    print("✅ Bot check শেষ!")

if __name__ == '__main__':
    main()

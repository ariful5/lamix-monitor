import os
import json
import base64
import requests
from datetime import datetime, timezone, timedelta

# ─── Config ───────────────────────────────────────────────
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

# ─── GitHub Storage ───────────────────────────────────────
def gh_get(filename):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    r = requests.get(url, headers=GH_HEADERS, timeout=10)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data['content']).decode()
        return content, data['sha']
    return None, None

def gh_save(filename, content_str, sha=None, msg="Update"):
    """Save file to GitHub. Returns new SHA if successful, None if failed."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    content = base64.b64encode(content_str.encode()).decode()
    body = {'message': msg, 'content': content}
    if sha:
        body['sha'] = sha
    r = requests.put(url, headers=GH_HEADERS, json=body, timeout=10)
    if r.status_code in [200, 201]:
        # ✅ FIX: নতুন SHA return করো
        return r.json().get('content', {}).get('sha')
    print(f"❌ gh_save failed [{r.status_code}]: {r.text[:200]}")
    return None

def load_config():
    raw, sha = gh_get(CONFIG_FILE)
    if raw:
        return json.loads(raw), sha
    return {}, None

def save_config(config, sha=None):
    """Returns new SHA or None on failure."""
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

# ─── Telegram API ─────────────────────────────────────────
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
        f"⚡ <b>Command দিয়ে:</b>\n"
        f"<code>/approve {uid}</code>\n"
        f"<code>/reject {uid}</code>\n\n"
        f"অথবা উপরের বাটন চাপুন (১ মিনিট পরে কাজ করবে)।",
        reply_markup=markup)

# ─── Command Handlers ─────────────────────────────────────
def handle_start(uid, name, username, config, sha):
    """Returns (config, sha)"""
    uid_str = str(uid)

    if uid_str == str(ADMIN_ID):
        if uid_str not in config:
            config[uid_str] = {'name': name, 'status': STATUS_APPROVED, 'keywords': []}
            new_sha = save_config(config, sha)
            if new_sha:
                sha = new_sha
        send(uid,
            f"👑 স্বাগতম Admin <b>{name}</b>!\n\n"
            f"🛡 <b>Admin কমান্ড:</b>\n"
            f"/users — সব user দেখুন\n"
            f"/approve ID — approve করুন\n"
            f"/reject ID — reject করুন\n"
            f"/revoke ID — access বন্ধ করুন\n\n"
            f"📋 <b>নিজের কমান্ড:</b>\n"
            f"/add /remove /list")
        return config, sha

    # ✅ FIX: user আগে থেকে আছে কিনা চেক করো
    if uid_str not in config:
        # নতুন user — config-এ add করো এবং admin-কে জানাও
        config[uid_str] = {'name': name, 'status': STATUS_PENDING, 'keywords': []}
        new_sha = save_config(config, sha)
        if new_sha:
            sha = new_sha
            # ✅ Save সফল হলে তবেই admin-কে জানাও
            notify_admin(uid, name, username)
            send(uid,
                f"👋 হ্যালো <b>{name}</b>!\n\n"
                f"⏳ <b>Waiting for Approval...</b>\n\n"
                f"আপনার request Admin-এর কাছে পাঠানো হয়েছে।\n"
                f"Approve হলে আপনাকে জানানো হবে। 🔔")
        else:
            # Save fail হলে config থেকে সরিয়ে দাও
            del config[uid_str]
            send(uid, "⚠️ সার্ভার সমস্যা। একটু পরে আবার /start দিন।")
        return config, sha

    # ইতিমধ্যে config-এ আছে
    status = config[uid_str].get('status')
    if status == STATUS_APPROVED:
        send(uid,
            f"👋 স্বাগতম <b>{name}</b>!\n\n"
            f"🤖 <b>Lamix Alert Bot</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>কমান্ড:</b>\n"
            f"▶ /add keyword — keyword যোগ\n"
            f"▶ /remove keyword — keyword মুছুন\n"
            f"▶ /list — সব keyword দেখুন")
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
    """Returns (config, sha)"""
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
        config[uid_str] = {'name': '', 'status': STATUS_APPROVED, 'keywords': []}
    if keyword in config[uid_str]['keywords']:
        send(uid, f"⚠️ <b>{keyword}</b> আগে থেকেই আছে!")
        return config, sha
    if len(config[uid_str]['keywords']) >= 10:
        send(uid, "❌ সর্বোচ্চ ১০টা keyword রাখা যাবে।")
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
    """Returns (config, sha)"""
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
    if not keywords:
        send(uid, "📋 কোনো keyword নেই।\n<code>/add example.com</code> দিয়ে যোগ করুন।")
        return
    lines = '\n'.join([f"  {i+1}. <code>{kw}</code>" for i, kw in enumerate(keywords)])
    send(uid, f"📋 <b>আপনার Keywords ({len(keywords)}/10)</b>\n\n{lines}")

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
            text += f"  • {d.get('name','?')} | <code>{u}</code> | {len(d.get('keywords',[]))} kw\n"
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

def handle_approve_reject_revoke(uid, text, config, sha, action):
    """Returns (config, sha)"""
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
    """Returns (config, sha)"""
    uid  = callback['from']['id']
    data = callback.get('data', '')

    if str(uid) != str(ADMIN_ID):
        return config, sha

    if data.startswith("approve_"):
        target = data.replace("approve_", "")
        if target in config:
            config[target]['status'] = STATUS_APPROVED
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

# ─── Main ─────────────────────────────────────────────────
def main():
    print("🤖 Bot check শুরু...")

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

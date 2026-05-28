import os
import json
import base64
import requests
from datetime import datetime, timedelta

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
           {"command": "start",      "description": "🤖 Bot শুরু করুন"},
           {"command": "add",        "description": "➕ CLI Keyword যোগ করুন"},
           {"command": "remove",     "description": "➖ CLI Keyword মুছুন"},
           {"command": "addbody",    "description": "➕ Body Keyword যোগ করুন"},
           {"command": "removebody", "description": "➖ Body Keyword মুছুন"},
           {"command": "list",       "description": "📋 সব keyword দেখুন"},
           {"command": "pause",      "description": "⏸ Keyword সাময়িক বন্ধ করুন"},
           {"command": "resume",     "description": "▶️ Keyword আবার চালু করুন"},
       ],
       scope={"type": "default"})
    if ADMIN_ID:
        tg('setMyCommands',
           commands=[
               {"command": "start",      "description": "🤖 Bot শুরু করুন"},
               {"command": "add",        "description": "➕ CLI Keyword যোগ করুন"},
               {"command": "remove",     "description": "➖ CLI Keyword মুছুন"},
               {"command": "addbody",    "description": "➕ Body Keyword যোগ করুন"},
               {"command": "removebody", "description": "➖ Body Keyword মুছুন"},
               {"command": "list",       "description": "📋 সব keyword দেখুন"},
               {"command": "pause",      "description": "⏸ Keyword সাময়িক বন্ধ করুন"},
               {"command": "resume",     "description": "▶️ Keyword আবার চালু করুন"},
               {"command": "users",      "description": "👥 সব user দেখুন"},
               {"command": "approve",    "description": "✅ User approve করুন"},
               {"command": "reject",     "description": "❌ User reject করুন"},
               {"command": "revoke",     "description": "🚫 Access বন্ধ করুন"},
               {"command": "notice",     "description": "📢 সবাইকে notice পাঠান"},
               {"command": "setlimit",   "description": "🔢 User limit পরিবর্তন করুন"},
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
                'body_keywords': [],
                'paused_keywords': {},
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
            f"/add /remove — CLI keyword\n"
            f"/addbody /removebody — Body keyword\n"
            f"/pause keyword 30 — keyword বন্ধ করুন\n"
            f"/resume keyword — keyword চালু করুন\n"
            f"/list — সব দেখুন")
        return config, sha

    if uid_str not in config:
        config[uid_str] = {
            'name': name,
            'status': STATUS_PENDING,
            'keywords': [],
            'body_keywords': [],
            'paused_keywords': {},
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
            f"⚙️ <b>CLI Search কমান্ড:</b>\n"
            f"▶ /add keyword — CLI keyword যোগ\n"
            f"▶ /remove keyword — CLI keyword মুছুন\n\n"
            f"🔎 <b>Body Search কমান্ড:</b>\n"
            f"▶ /addbody keyword — Body keyword যোগ\n"
            f"▶ /removebody keyword — Body keyword মুছুন\n\n"
            f"⏸ <b>Pause কমান্ড:</b>\n"
            f"▶ /pause keyword 30 — 30 মিনিট বন্ধ\n"
            f"▶ /resume keyword — এখনই চালু\n\n"
            f"▶ /list — সব keyword দেখুন\n\n"
            f"📊 আপনার limit: <b>{limit}</b> টা keyword (CLI + Body মিলিয়ে)")
    elif status == STATUS_PENDING:
        send(uid, "⏳ আপনার request এখনো pending। একটু অপেক্ষা করুন।")
    elif status == STATUS_BANNED:
        send(uid, "🚫 দুঃখিত, আপনার access বন্ধ করা হয়েছে।")

    return config, sha

def check_access(uid_str, config):
    if uid_str == str(ADMIN_ID):
        return True
    return config.get(uid_str, {}).get('status') == STATUS_APPROVED

def _ensure_body_keywords(config, uid_str):
    if 'body_keywords' not in config.get(uid_str, {}):
        config[uid_str]['body_keywords'] = []

def _ensure_paused_keywords(config, uid_str):
    if 'paused_keywords' not in config.get(uid_str, {}):
        config[uid_str]['paused_keywords'] = {}

def is_keyword_active(uid_str, keyword, config):
    _ensure_paused_keywords(config, uid_str)
    paused = config[uid_str]['paused_keywords']
    if keyword not in paused:
        return True
    resume_time = datetime.fromisoformat(paused[keyword])
    if datetime.utcnow() >= resume_time:
        del config[uid_str]['paused_keywords'][keyword]
        return True
    return False

def handle_pause(uid, text, config, sha):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return config, sha
    parts = text.split()
    if len(parts) < 2:
        send(uid,
            "⚠️ ব্যবহার:\n"
            "<code>/pause keyword</code> — 30 মিনিট (default)\n"
            "<code>/pause keyword 60</code> — 60 মিনিট")
        return config, sha
    keyword = parts[1].strip().lower()
    minutes = 30
    if len(parts) >= 3:
        try:
            minutes = int(parts[2])
            if minutes < 1:
                raise ValueError
        except:
            send(uid, "❌ মিনিট সংখ্যা সঠিক নয়। (যেমন: 30, 60)")
            return config, sha
    _ensure_body_keywords(config, uid_str)
    _ensure_paused_keywords(config, uid_str)
    cli_kws  = config.get(uid_str, {}).get('keywords', [])
    body_kws = config.get(uid_str, {}).get('body_keywords', [])
    if keyword not in cli_kws and keyword not in body_kws:
        send(uid, f"❌ <b>{keyword}</b> আপনার list এ নেই!")
        return config, sha
    resume_time = datetime.utcnow() + timedelta(minutes=minutes)
    config[uid_str]['paused_keywords'][keyword] = resume_time.isoformat()
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        bd_time = resume_time + timedelta(hours=6)
        send(uid,
            f"⏸ <b>{keyword}</b> বন্ধ করা হয়েছে!\n\n"
            f"⏱ সময়: <b>{minutes} মিনিট</b>\n"
            f"🕐 আবার চালু হবে: <b>{bd_time.strftime('%I:%M %p')}</b> (BD সময়)\n\n"
            f"আগেই চালু করতে: <code>/resume {keyword}</code>")
    else:
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_resume(uid, text, config, sha):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return config, sha
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send(uid, "⚠️ লিখুন: <code>/resume keyword</code>")
        return config, sha
    keyword = parts[1].strip().lower()
    _ensure_paused_keywords(config, uid_str)
    paused = config[uid_str]['paused_keywords']
    if keyword not in paused:
        send(uid, f"⚠️ <b>{keyword}</b> pause এ নেই!")
        return config, sha
    del config[uid_str]['paused_keywords'][keyword]
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        send(uid, f"▶️ <b>{keyword}</b> এখনই চালু করা হয়েছে!")
    else:
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

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
        config[uid_str] = {'name': '', 'status': STATUS_APPROVED, 'keywords': [], 'body_keywords': [], 'paused_keywords': {}, 'limit': DEFAULT_LIMIT}
    _ensure_body_keywords(config, uid_str)
    _ensure_paused_keywords(config, uid_str)
    if keyword in config[uid_str]['keywords']:
        send(uid, f"⚠️ <b>{keyword}</b> CLI list-এ আগে থেকেই আছে!")
        return config, sha
    is_admin = (uid_str == str(ADMIN_ID))
    limit = 999 if is_admin else config[uid_str].get('limit', DEFAULT_LIMIT)
    total_keywords = len(config[uid_str]['keywords']) + len(config[uid_str]['body_keywords'])
    if total_keywords >= limit:
        if not is_admin:
            send(uid,
                f"❌ আপনার limit ({limit}) পূর্ণ!\n\n"
                f"পুরনোটা মুছে নতুন যোগ করুন:\n"
                f"<code>/remove keyword</code> বা <code>/removebody keyword</code>")
        return config, sha
    config[uid_str]['keywords'].append(keyword)
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        total = len(config[uid_str]['keywords']) + len(config[uid_str]['body_keywords'])
        send(uid, f"✅ CLI keyword <b>{keyword}</b> যোগ হয়েছে!\n📊 মোট: <b>{total}/{limit}</b> keywords")
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
        send(uid, f"❌ <b>{keyword}</b> আপনার CLI list-এ নেই!")
        return config, sha
    config[uid_str]['keywords'].remove(keyword)
    _ensure_paused_keywords(config, uid_str)
    config[uid_str]['paused_keywords'].pop(keyword, None)
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        _ensure_body_keywords(config, uid_str)
        total = len(config[uid_str]['keywords']) + len(config[uid_str]['body_keywords'])
        limit = config[uid_str].get('limit', DEFAULT_LIMIT)
        send(uid, f"🗑 CLI keyword <b>{keyword}</b> সরানো হয়েছে!\n📊 বাকি: <b>{total}/{limit}</b> keywords")
    else:
        config[uid_str]['keywords'].append(keyword)
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_addbody(uid, text, config, sha):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return config, sha
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send(uid, "⚠️ লিখুন: <code>/addbody otp</code>")
        return config, sha
    keyword = parts[1].strip().lower()
    if uid_str not in config:
        config[uid_str] = {'name': '', 'status': STATUS_APPROVED, 'keywords': [], 'body_keywords': [], 'paused_keywords': {}, 'limit': DEFAULT_LIMIT}
    _ensure_body_keywords(config, uid_str)
    _ensure_paused_keywords(config, uid_str)
    if keyword in config[uid_str]['body_keywords']:
        send(uid, f"⚠️ <b>{keyword}</b> Body list-এ আগে থেকেই আছে!")
        return config, sha
    is_admin = (uid_str == str(ADMIN_ID))
    limit = 999 if is_admin else config[uid_str].get('limit', DEFAULT_LIMIT)
    total_keywords = len(config[uid_str]['keywords']) + len(config[uid_str]['body_keywords'])
    if total_keywords >= limit:
        if not is_admin:
            send(uid,
                f"❌ আপনার limit ({limit}) পূর্ণ!\n\n"
                f"পুরনোটা মুছে নতুন যোগ করুন:\n"
                f"<code>/remove keyword</code> বা <code>/removebody keyword</code>")
        return config, sha
    config[uid_str]['body_keywords'].append(keyword)
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        total = len(config[uid_str]['keywords']) + len(config[uid_str]['body_keywords'])
        send(uid, f"✅ Body keyword <b>{keyword}</b> যোগ হয়েছে!\n📊 মোট: <b>{total}/{limit}</b> keywords")
    else:
        config[uid_str]['body_keywords'].remove(keyword)
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_removebody(uid, text, config, sha):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return config, sha
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send(uid, "⚠️ লিখুন: <code>/removebody otp</code>")
        return config, sha
    keyword = parts[1].strip().lower()
    _ensure_body_keywords(config, uid_str)
    _ensure_paused_keywords(config, uid_str)
    if keyword not in config.get(uid_str, {}).get('body_keywords', []):
        send(uid, f"❌ <b>{keyword}</b> আপনার Body list-এ নেই!")
        return config, sha
    config[uid_str]['body_keywords'].remove(keyword)
    config[uid_str]['paused_keywords'].pop(keyword, None)
    new_sha = save_config(config, sha)
    if new_sha:
        sha = new_sha
        total = len(config[uid_str]['keywords']) + len(config[uid_str]['body_keywords'])
        limit = config[uid_str].get('limit', DEFAULT_LIMIT)
        send(uid, f"🗑 Body keyword <b>{keyword}</b> সরানো হয়েছে!\n📊 বাকি: <b>{total}/{limit}</b> keywords")
    else:
        config[uid_str]['body_keywords'].append(keyword)
        send(uid, "⚠️ সংরক্ষণ ব্যর্থ। আবার চেষ্টা করুন।")
    return config, sha

def handle_list(uid, config):
    uid_str = str(uid)
    if not check_access(uid_str, config):
        send(uid, "⛔ আপনার access নেই।")
        return
    _ensure_body_keywords(config, uid_str)
    _ensure_paused_keywords(config, uid_str)
    cli_keywords  = config.get(uid_str, {}).get('keywords', [])
    body_keywords = config.get(uid_str, {}).get('body_keywords', [])
    paused        = config.get(uid_str, {}).get('paused_keywords', {})
    limit = config.get(uid_str, {}).get('limit', DEFAULT_LIMIT)
    total = len(cli_keywords) + len(body_keywords)
    now   = datetime.utcnow()

    if not cli_keywords and not body_keywords:
        send(uid,
            f"📋 কোনো keyword নেই।\n\n"
            f"<code>/add keyword</code> — CLI যোগ করুন\n"
            f"<code>/addbody keyword</code> — Body যোগ করুন")
        return

    text = f"📋 <b>আপনার Keywords ({total}/{limit})</b>\n"

    def kw_line(i, kw):
        if kw in paused:
            resume = datetime.fromisoformat(paused[kw])
            if now < resume:
                mins_left = int((resume - now).total_seconds() / 60) + 1
                return f"  {i}. <code>{kw}</code> ⏸ ({mins_left} মিনিট বাকি)\n"
        return f"  {i}. <code>{kw}</code> ✅\n"

    if cli_keywords:
        text += f"\n🌐 <b>CLI Search ({len(cli_keywords)})</b>\n"
        for i, kw in enumerate(cli_keywords, 1):
            text += kw_line(i, kw)

    if body_keywords:
        text += f"\n🔎 <b>Body Search ({len(body_keywords)})</b>\n"
        for i, kw in enumerate(body_keywords, 1):
            text += kw_line(i, kw)

    text += f"\n⏸ = বন্ধ  ✅ = চালু\n"
    text += f"<code>/pause keyword 30</code> — বন্ধ করুন"
    send(uid, text)

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
            cli_kw  = len(d.get('keywords', []))
            body_kw = len(d.get('body_keywords', []))
            paused  = len(d.

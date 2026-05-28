import requests
from bs4 import BeautifulSoup
import os
import re
import json
import random
import base64
from datetime import datetime, timezone, timedelta
import time

# ─── Config ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
GITHUB_TOKEN   = os.environ.get('MY_PAT_TOKEN', '')
GITHUB_REPO    = os.environ.get('GITHUB_REPO', 'ariful5/my-project-2024')
CONFIG_FILE    = 'users_config.json'
STATE_FILE     = 'monitor_state.json'
ALERT_GROUP_ID = os.environ.get('ALERT_GROUP_ID', '')

GH_HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
]

HEADERS = {
    'User-Agent': random.choice(USER_AGENTS),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Origin': 'https://lamix.org',
    'Referer': 'https://lamix.org/tools',
}

STATUS_APPROVED = 'approved'
MAX_SESSION_FAIL = 3  # টানা কতটা session fail হলে alert পাঠাবে

IGNORE_EXACT = {
    'search', 'results', 'search results', 'cli', 'cli search',
    'tools', 'toggle', 'mode', 'submit', 'loading', 'please', 'wait',
    'show', 'hide', 'more', 'less', 'next', 'prev',
    'country', 'countries', 'message', 'body', 'minute',
    'access', 'last', 'find', 'result', 'keyword',
    'lamix', 'sms', 'tool', 'in', 'the', 'from', 'out',
    'search in message body',
    'find out access from a specific cli in the last 30 minute',
    'lamix cli search tool',
}

VALID_COUNTRIES = {
    "Afghanistan","Albania","Algeria","Andorra","Angola","Argentina","Armenia",
    "Australia","Austria","Azerbaijan","Bahamas","Bahrain","Bangladesh","Belarus",
    "Belgium","Belize","Benin","Bhutan","Bolivia","Bosnia","Botswana","Brazil",
    "Brunei","Bulgaria","Burkina Faso","Burundi","Cambodia","Cameroon","Canada",
    "Chad","Chile","China","Colombia","Comoros","Congo","Croatia","Cuba",
    "Cyprus","Czech Republic","Denmark","Djibouti","Dominican Republic","Ecuador",
    "Egypt","El Salvador","Eritrea","Estonia","Ethiopia","Fiji","Finland","France",
    "Gabon","Gambia","Georgia","Germany","Ghana","Greece","Guatemala","Guinea",
    "Guyana","Haiti","Honduras","Hungary","Iceland","India","Indonesia","Iran",
    "Iraq","Ireland","Israel","Italy","Jamaica","Japan","Jordan","Kazakhstan",
    "Kenya","Kuwait","Kyrgyzstan","Laos","Latvia","Lebanon","Lesotho","Liberia",
    "Libya","Lithuania","Luxembourg","Madagascar","Malawi","Malaysia","Maldives",
    "Mali","Malta","Mauritania","Mauritius","Mexico","Moldova","Mongolia",
    "Montenegro","Morocco","Mozambique","Myanmar","Namibia","Nepal","Netherlands",
    "Nicaragua","Niger","Nigeria","Norway","Oman","Pakistan","Palestine","Panama",
    "Paraguay","Peru","Philippines","Poland","Portugal","Qatar","Romania","Russia",
    "Rwanda","Saudi Arabia","Senegal","Serbia","Sierra Leone","Singapore",
    "Slovakia","Slovenia","Somalia","South Africa","South Sudan","Spain",
    "Sri Lanka","Sudan","Suriname","Sweden","Switzerland","Syria","Taiwan",
    "Tajikistan","Tanzania","Thailand","Togo","Trinidad and Tobago","Tunisia",
    "Turkey","Turkmenistan","Uganda","Ukraine","United Arab Emirates",
    "United Kingdom","United States","Uruguay","Uzbekistan","Venezuela",
    "Vietnam","Yemen","Zambia","Zimbabwe","Ivory Coast","North Korea",
    "South Korea","New Zealand","Papua New Guinea","North Macedonia",
    "East Timor","Kosovo","UAE","USA","UK","Cabo Verde","Central African Republic",
    "Democratic Republic of Congo","Equatorial Guinea","Burkina",
}

VALID_COUNTRIES_LOWER = {c.lower(): c for c in VALID_COUNTRIES}

COUNTRY_FLAGS = {
    "Afghanistan":"🇦🇫","Albania":"🇦🇱","Algeria":"🇩🇿","Andorra":"🇦🇩",
    "Angola":"🇦🇴","Argentina":"🇦🇷","Armenia":"🇦🇲","Australia":"🇦🇺",
    "Austria":"🇦🇹","Azerbaijan":"🇦🇿","Bahamas":"🇧🇸","Bahrain":"🇧🇭",
    "Bangladesh":"🇧🇩","Belarus":"🇧🇾","Belgium":"🇧🇪","Belize":"🇧🇿",
    "Benin":"🇧🇯","Bhutan":"🇧🇹","Bolivia":"🇧🇴","Bosnia":"🇧🇦",
    "Botswana":"🇧🇼","Brazil":"🇧🇷","Brunei":"🇧🇳","Bulgaria":"🇧🇬",
    "Burkina Faso":"🇧🇫","Burundi":"🇧🇮","Cambodia":"🇰🇭","Cameroon":"🇨🇲",
    "Canada":"🇨🇦","Chad":"🇹🇩","Chile":"🇨🇱","China":"🇨🇳",
    "Colombia":"🇨🇴","Comoros":"🇰🇲","Congo":"🇨🇬","Croatia":"🇭🇷",
    "Cuba":"🇨🇺","Cyprus":"🇨🇾","Czech Republic":"🇨🇿","Denmark":"🇩🇰",
    "Djibouti":"🇩🇯","Dominican Republic":"🇩🇴","Ecuador":"🇪🇨",
    "Egypt":"🇪🇬","El Salvador":"🇸🇻","Eritrea":"🇪🇷","Estonia":"🇪🇪",
    "Ethiopia":"🇪🇹","Fiji":"🇫🇯","Finland":"🇫🇮","France":"🇫🇷",
    "Gabon":"🇬🇦","Gambia":"🇬🇲","Georgia":"🇬🇪","Germany":"🇩🇪",
    "Ghana":"🇬🇭","Greece":"🇬🇷","Guatemala":"🇬🇹","Guinea":"🇬🇳",
    "Guyana":"🇬🇾","Haiti":"🇭🇹","Honduras":"🇭🇳","Hungary":"🇭🇺",
    "Iceland":"🇮🇸","India":"🇮🇳","Indonesia":"🇮🇩","Iran":"🇮🇷",
    "Iraq":"🇮🇶","Ireland":"🇮🇪","Israel":"🇮🇱","Italy":"🇮🇹",
    "Jamaica":"🇯🇲","Japan":"🇯🇵","Jordan":"🇯🇴","Kazakhstan":"🇰🇿",
    "Kenya":"🇰🇪","Kuwait":"🇰🇼","Kyrgyzstan":"🇰🇬","Laos":"🇱🇦",
    "Latvia":"🇱🇻","Lebanon":"🇱🇧","Lesotho":"🇱🇸","Liberia":"🇱🇷",
    "Libya":"🇱🇾","Lithuania":"🇱🇹","Luxembourg":"🇱🇺","Madagascar":"🇲🇬",
    "Malawi":"🇲🇼","Malaysia":"🇲🇾","Maldives":"🇲🇻","Mali":"🇲🇱",
    "Malta":"🇲🇹","Mauritania":"🇲🇷","Mauritius":"🇲🇺","Mexico":"🇲🇽",
    "Moldova":"🇲🇩","Mongolia":"🇲🇳","Montenegro":"🇲🇪","Morocco":"🇲🇦",
    "Mozambique":"🇲🇿","Myanmar":"🇲🇲","Namibia":"🇳🇦","Nepal":"🇳🇵",
    "Netherlands":"🇳🇱","Nicaragua":"🇳🇮","Niger":"🇳🇪","Nigeria":"🇳🇬",
    "Norway":"🇳🇴","Oman":"🇴🇲","Pakistan":"🇵🇰","Palestine":"🇵🇸",
    "Panama":"🇵🇦","Paraguay":"🇵🇾","Peru":"🇵🇪","Philippines":"🇵🇭",
    "Poland":"🇵🇱","Portugal":"🇵🇹","Qatar":"🇶🇦","Romania":"🇷🇴",
    "Russia":"🇷🇺","Rwanda":"🇷🇼","Saudi Arabia":"🇸🇦","Senegal":"🇸🇳",
    "Serbia":"🇷🇸","Sierra Leone":"🇸🇱","Singapore":"🇸🇬","Slovakia":"🇸🇰",
    "Slovenia":"🇸🇮","Somalia":"🇸🇴","South Africa":"🇿🇦","South Sudan":"🇸🇸",
    "Spain":"🇪🇸","Sri Lanka":"🇱🇰","Sudan":"🇸🇩","Suriname":"🇸🇷",
    "Sweden":"🇸🇪","Switzerland":"🇨🇭","Syria":"🇸🇾","Taiwan":"🇹🇼",
    "Tajikistan":"🇹🇯","Tanzania":"🇹🇿","Thailand":"🇹🇭","Togo":"🇹🇬",
    "Trinidad and Tobago":"🇹🇹","Tunisia":"🇹🇳","Turkey":"🇹🇷",
    "Turkmenistan":"🇹🇲","Uganda":"🇺🇬","Ukraine":"🇺🇦",
    "United Arab Emirates":"🇦🇪","UAE":"🇦🇪","United Kingdom":"🇬🇧",
    "UK":"🇬🇧","United States":"🇺🇸","USA":"🇺🇸","Uruguay":"🇺🇾",
    "Uzbekistan":"🇺🇿","Venezuela":"🇻🇪","Vietnam":"🇻🇳","Yemen":"🇾🇪",
    "Zambia":"🇿🇲","Zimbabwe":"🇿🇼","Ivory Coast":"🇨🇮","North Korea":"🇰🇵",
    "South Korea":"🇰🇷","New Zealand":"🇳🇿","Papua New Guinea":"🇵🇬",
    "North Macedonia":"🇲🇰","East Timor":"🇹🇱","Kosovo":"🇽🇰",
    "Cabo Verde":"🇨🇻","Central African Republic":"🇨🇫",
    "Democratic Republic of Congo":"🇨🇩","Equatorial Guinea":"🇬🇶",
    "Burkina":"🇧🇫",
}


# ─── Pause / Active Check ─────────────────────────────────

def is_keyword_active(uid_str, keyword, udata):
    paused = udata.get('paused_keywords', {})
    if keyword not in paused:
        return True
    try:
        resume_time = datetime.fromisoformat(paused[keyword])
    except Exception:
        return True
    if datetime.utcnow() >= resume_time:
        return True
    return False


# ─── GitHub Config Load ───────────────────────────────────

def load_user_config():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_FILE}"
    try:
        r = requests.get(url, headers=GH_HEADERS, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode()
            return json.loads(content)
    except Exception as e:
        print(f"   Config load error: {e}")
    return {}


# ─── GitHub State Load / Save ────────────────────────────
# monitor_state.json এ টানা failure count রাখা হয়
# Format: { "cli:keyword": 2, "body:keyword": 1, ... }

def load_monitor_state():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    try:
        r = requests.get(url, headers=GH_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data['content']).decode()
            state = json.loads(content)
            state['_sha'] = data['sha']
            return state
    except Exception as e:
        print(f"   State load error: {e}")
    return {}


def save_monitor_state(state):
    sha = state.pop('_sha', None)
    content = base64.b64encode(json.dumps(state, indent=2).encode()).decode()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATE_FILE}"
    payload = {
        'message': 'Update monitor state',
        'content': content,
    }
    if sha:
        payload['sha'] = sha
    try:
        r = requests.put(url, headers=GH_HEADERS, json=payload, timeout=10)
        if r.status_code in (200, 201):
            print(f"   State saved.")
        else:
            print(f"   State save error: {r.status_code}")
    except Exception as e:
        print(f"   State save exception: {e}")


# ─── Text Helpers ─────────────────────────────────────────

def clean_text(txt):
    txt = re.sub(r'[\U0001F000-\U0001FFFF]', '', txt)
    txt = re.sub(r'\s+', ' ', txt)
    return txt.strip()


def is_result_entry(txt):
    if not txt or len(txt) < 3 or len(txt) > 80:
        return False
    if txt.lower() in IGNORE_EXACT:
        return False
    parts = re.split(r'\s*[-–]\s*', txt, maxsplit=1)
    country_part = parts[0].strip()
    return country_part.lower() in VALID_COUNTRIES_LOWER


def get_canonical(txt):
    parts = re.split(r'\s*[-–]\s*', txt, maxsplit=1)
    country_part = parts[0].strip()
    canonical_country = VALID_COUNTRIES_LOWER.get(country_part.lower(), country_part)
    if len(parts) > 1:
        return f"{canonical_country} - {parts[1].strip()}"
    return canonical_country


def get_flag(entry):
    parts = re.split(r'\s*[-–]\s*', entry, maxsplit=1)
    country = parts[0].strip()
    return COUNTRY_FLAGS.get(country, "🌍")


# ─── Scraper ──────────────────────────────────────────────

def search(keyword, search_in_body=False):
    # প্রতিটা request-এ নতুন random UA
    HEADERS['User-Agent'] = random.choice(USER_AGENTS)
    session = requests.Session()
    session.headers.update(HEADERS)
    resp = session.get('https://lamix.org/tools', timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    token_el = soup.find('input', {'name': '_token'})
    token = token_el['value'] if token_el else ''

    data = {
        '_token': token,
        'search_term': keyword.strip(),
        'search_in_body': '1' if search_in_body else '0',
        'g-recaptcha-response': '',
    }
    if search_in_body:
        data['toggle_mode'] = 'on'

    resp = session.post('https://lamix.org/tools', data=data, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_results(html):
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    seen = set()

    for li in soup.find_all('li'):
        txt = clean_text(li.get_text(separator=' ', strip=True))
        if txt and txt.lower() not in seen and is_result_entry(txt):
            canonical = get_canonical(txt)
            if canonical.lower() not in seen:
                results.append(canonical)
                seen.add(canonical.lower())

    if not results:
        for el in soup.find_all(True, class_=re.compile(r'country|result|item|cli|row|card|entry', re.I)):
            if not el.find():
                txt = clean_text(el.get_text(strip=True))
                if txt and txt.lower() not in seen and is_result_entry(txt):
                    canonical = get_canonical(txt)
                    if canonical.lower() not in seen:
                        results.append(canonical)
                        seen.add(canonical.lower())

    if not results:
        for el in soup.find_all(['td', 'span', 'p']):
            if not el.find():
                txt = clean_text(el.get_text(strip=True))
                if txt and txt.lower() not in seen and is_result_entry(txt):
                    canonical = get_canonical(txt)
                    if canonical.lower() not in seen:
                        results.append(canonical)
                        seen.add(canonical.lower())

    return results


def do_search_with_retry(keyword, search_in_body=False, max_retry=3):
    """
    প্রতিটা attempt-এ নতুন random UA দিয়ে try করে।
    captcha বা error হলে 5 সেকেন্ড অপেক্ষা করে পরের attempt।
    ৩ attempt-এ সর্বোচ্চ ~২.৫ মিনিট।
    """
    mode_label = "BODY" if search_in_body else "CLI"
    print(f"\n Search [{mode_label}]: '{keyword}'")

    for attempt in range(1, max_retry + 1):
        ua = random.choice(USER_AGENTS)
        HEADERS['User-Agent'] = ua
        print(f"   Attempt {attempt}/{max_retry} | UA: ...{ua[-30:]}")

        try:
            html = search(keyword, search_in_body=search_in_body)

            if 'recaptcha' in html.lower() and len(html) < 2000:
                print(f"   reCAPTCHA detected! Switching UA...")
                if attempt < max_retry:
                    time.sleep(5)
                    continue
                return 'captcha'

            results = parse_results(html)
            print(f"   Results: {results}")
            return results

        except Exception as e:
            print(f"   Error: {e}")
            if attempt < max_retry:
                print(f"   Waiting 5s before retry...")
                time.sleep(5)

    print(f"   All {max_retry} attempts failed")
    return 'error'


# ─── Telegram ─────────────────────────────────────────────

def send_telegram(chat_id, message, reply_markup=None):
    if not TELEGRAM_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            print(f"   Sent to {chat_id}")
        else:
            print(f"   Error {chat_id}: {resp.status_code} | {resp.text}")
        return resp.status_code == 200
    except Exception as e:
        print(f"   Exception {chat_id}: {e}")
        return False


# ─── Alert Sender ─────────────────────────────────────────

def _send_result(uid, name, keyword, result,
                 time_str, date_str,
                 is_body_search=False,
                 reply_markup=None):

    search_label = "Body" if is_body_search else "CLI"

    if result in ('captcha', 'error'):
        # single session fail → কোনো বার্তা পাঠাবে না
        print(f"   [{search_label}] '{keyword}' session failed ({result}) — no alert sent")
        return

    elif result:
        country_lines = ''
        for i, r in enumerate(result, 1):
            flag = get_flag(r)
            country_lines += f"{i}. {r} {flag}\n"

        search_icon  = "🔎" if is_body_search else "🌐"
        body_or_cli  = "🔎 Body Search" if is_body_search else "🌐 CLI Search"

        personal_msg = (
            f"{search_icon}💥 <b>LIVE ALERT</b> 💥{search_icon}\n\n"
            f"{body_or_cli}\n"
            f"🎯 Keyword » <b>{keyword}</b>\n"
            f"📍 Countries » <b>{len(result)}</b>\n\n"
            f"{country_lines}\n"
            f"⏰ {time_str} | {date_str}"
        )
        send_telegram(uid, personal_msg, reply_markup)

        alert_group = os.environ.get('ALERT_GROUP_ID', '')
        if alert_group:
            group_msg = (
                f"👤 <b>{name}</b>\n\n"
                f"{search_icon}💥 <b>LIVE ALERT</b> 💥{search_icon}\n\n"
                f"{body_or_cli}\n"
                f"🎯 Keyword » <b>{keyword}</b>\n"
                f"📍 Countries » <b>{len(result)}</b>\n\n"
                f"{country_lines}\n"
                f"⏰ {time_str} | {date_str}"
            )
            send_telegram(int(alert_group), group_msg)

    else:
        print(f"   [{search_label}] {keyword} -> No results")


# ─── Consecutive Failure Alert ────────────────────────────

def send_consecutive_fail_alert(uid, name, keyword, fail_count, mode_label, time_str, date_str):
    """টানা ৩ session fail হলে এই বার্তা পাঠাবে।"""
    msg = (
        f"🚨 <b>CONSECUTIVE FAIL ALERT</b> 🚨\n\n"
        f"👤 User: <b>{name}</b>\n"
        f"🔍 Mode: <b>{mode_label}</b>\n"
        f"🎯 Keyword: <code>{keyword}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"❌ টানা <b>{fail_count} বার</b> search fail হয়েছে!\n"
        f"প্রতিটা session-এ ৩ বার retry করেও\n"
        f"কোনো result পাওয়া যায়নি।\n\n"
        f"⚠️ সম্ভাব্য কারণ:\n"
        f"• Site reCAPTCHA block করছে\n"
        f"• Server down আছে\n"
        f"• Network সমস্যা\n\n"
        f"⏰ {time_str} | {date_str}"
    )
    send_telegram(uid, msg)
    alert_group = os.environ.get('ALERT_GROUP_ID', '')
    if alert_group:
        send_telegram(int(alert_group), msg)


# ─── Main ─────────────────────────────────────────────────

def main():
    bd_tz = timezone(timedelta(hours=6))
    now = datetime.now(bd_tz)
    time_str = now.strftime('%I:%M %p')
    date_str = now.strftime('%d.%m.%y')

    print(f"Monitor start: {now.strftime('%Y-%m-%d %H:%M')}")

    user_config = load_user_config()
    if not user_config:
        print("   No user config found!")
        return

    monitor_state = load_monitor_state()

    approved_users = {
        uid: udata
        for uid, udata in user_config.items()
        if udata.get('status') == STATUS_APPROVED
    }

    if not approved_users:
        print("   No approved users!")
        return

    # ── Active keyword সংগ্রহ ──────────────────────────────
    all_cli_keywords  = set()
    all_body_keywords = set()

    for uid, udata in approved_users.items():
        for kw in udata.get('keywords', []):
            kw = kw.strip().lower()
            if kw and is_keyword_active(uid, kw, udata):
                all_cli_keywords.add(kw)

        for kw in udata.get('body_keywords', []):
            kw = kw.strip().lower()
            if kw and is_keyword_active(uid, kw, udata):
                all_body_keywords.add(kw)

    # ── Random order ────────────────────────────────────────
    cli_keywords_list  = list(all_cli_keywords)
    body_keywords_list = list(all_body_keywords)
    random.shuffle(cli_keywords_list)
    random.shuffle(body_keywords_list)

    print(f"   Active CLI keywords  : {len(cli_keywords_list)} → {cli_keywords_list}")
    print(f"   Active Body keywords : {len(body_keywords_list)} → {body_keywords_list}")

    # ── Search cache ────────────────────────────────────────
    cli_cache  = {}
    body_cache = {}

    for keyword in cli_keywords_list:
        cli_cache[keyword] = do_search_with_retry(keyword, search_in_body=False)

    for keyword in body_keywords_list:
        body_cache[keyword] = do_search_with_retry(keyword, search_in_body=True)

    # ── Failure state update ────────────────────────────────
    state_changed = False

    def update_fail_state(state_key, result, uid, name, mode_label):
        nonlocal state_changed
        if result in ('captcha', 'error'):
            prev = monitor_state.get(state_key, 0)
            monitor_state[state_key] = prev + 1
            state_changed = True
            print(f"   Fail count [{state_key}]: {monitor_state[state_key]}")
            if monitor_state[state_key] >= MAX_SESSION_FAIL:
                send_consecutive_fail_alert(
                    uid, name, state_key.split(':', 1)[1],
                    monitor_state[state_key], mode_label,
                    time_str, date_str
                )
                monitor_state[state_key] = 0  # reset after alert
        else:
            if monitor_state.get(state_key, 0) > 0:
                monitor_state[state_key] = 0
                state_changed = True

    reply_markup = {
        "inline_keyboard": [[
            {"text": "👨‍💻 Developer", "url": "https://t.me/Napa_Ex"},
        ]]
    }

    # ── প্রতিটি approved ইউজারকে alert পাঠাও ──────────────
    for uid, udata in approved_users.items():
        name = udata.get('name', 'User')

        cli_kws = [
            kw.strip().lower()
            for kw in udata.get('keywords', [])
            if kw.strip() and is_keyword_active(uid, kw.strip().lower(), udata)
        ]
        body_kws = [
            kw.strip().lower()
            for kw in udata.get('body_keywords', [])
            if kw.strip() and is_keyword_active(uid, kw.strip().lower(), udata)
        ]

        if not cli_kws and not body_kws:
            print(f"\n User: {name} ({uid}) — কোনো active keyword নেই, skip")
            continue

        print(f"\n User: {name} ({uid})")

        for keyword in cli_kws:
            result = cli_cache.get(keyword)
            state_key = f"cli:{keyword}"
            update_fail_state(state_key, result, uid, name, "🌐 CLI Search")
            _send_result(uid, name, keyword, result,
                         time_str, date_str,
                         is_body_search=False,
                         reply_markup=reply_markup)

        for keyword in body_kws:
            result = body_cache.get(keyword)
            state_key = f"body:{keyword}"
            update_fail_state(state_key, result, uid, name, "🔎 Body Search")
            _send_result(uid, name, keyword, result,
                         time_str, date_str,
                         is_body_search=True,
                         reply_markup=reply_markup)

    # ── State save ──────────────────────────────────────────
    if state_changed:
        save_monitor_state(monitor_state)

    print("\n Done!")


if __name__ == '__main__':
    main()

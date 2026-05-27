import requests
from bs4 import BeautifulSoup
import os
import re
import json
from datetime import datetime, timezone, timedelta
import time

# ─── Config ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
GITHUB_TOKEN   = os.environ.get('MY_PAT_TOKEN', '')
GITHUB_REPO    = os.environ.get('GITHUB_REPO', 'ariful5/lamix-monitor')
CONFIG_FILE    = 'users_config.json'
ALERT_GROUP_ID = os.environ.get('ALERT_GROUP_ID', '')

GH_HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Origin': 'https://lamix.org',
    'Referer': 'https://lamix.org/tools',
}

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


def get_flag(entry):
    parts = re.split(r'\s*[-–]\s*', entry, maxsplit=1)
    country = parts[0].strip()
    return COUNTRY_FLAGS.get(country, "🌍")


def load_user_config():
    import base64
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_FILE}"
    try:
        r = requests.get(url, headers=GH_HEADERS, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode()
            return json.loads(content)
    except Exception as e:
        print(f"   ⚠️ Config লোড error: {e}")
    return {}


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


def search(keyword, search_in_body=False):
    """
    search_in_body=False → normal CLI search (toggle OFF)
    search_in_body=True  → Message Body search (toggle ON)
    """
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
    """Retry logic সহ সার্চ করুন। 'captcha', 'error', বা list রিটার্ন করে।"""
    mode_label = "BODY" if search_in_body else "CLI"
    print(f"\n▶ Searching [{mode_label}]: '{keyword}'")

    for attempt in range(1, max_retry + 1):
        try:
            html = search(keyword, search_in_body=search_in_body)

            if 'recaptcha' in html.lower() and len(html) < 2000:
                print(f"   ⚠️ reCAPTCHA!")
                return 'captcha'

            results = parse_results(html)
            print(f"   ✅ Results: {results}")
            return results

        except Exception as e:
            print(f"   ❌ Attempt {attempt}/{max_retry} Error: {e}")
            if attempt < max_retry:
                print(f"   ⏳ ১০ সেকেন্ড অপেক্ষা...")
                time.sleep(10)

    print(f"   ❌ সব চেষ্টা শেষ")
    return 'error'


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
            print(f"   ✅ {chat_id} → পাঠানো সফল!")
        else:
            print(f"   ❌ {chat_id} → error: {resp.status_code} | {resp.text}")
        return resp.status_code == 200
    except Exception as e:
        print(f"   ❌ {chat_id} → exception: {e}")
        return False


def build_alert_message(name, keyword, results, time_str, date_str,
                        is_body_search=False, prefix=""):
    country_lines = ''
    for i, r in enumerate(results, 1):
        flag = get_flag(r)
        country_lines += f"{i}. {r} {flag}\n"

    search_label = "🔎 Body Search" if is_body_search else "🌐 CLI Search"

    prefix_line = f"👤 <b>{name}</b>\n\n" if prefix else ""
msg = (
            f"{prefix_line}"
            f"🌐💥 <b>LIVE ALERT</b> 💥🌐\n\n"
            f"{search_label}\n"
            f"🎯 Keyword » <b>{keyword}</b>\n"
            f"📍 Countries » <b>{len(results)}</b>\n\n"
            f"{country_lines}\n"
            f"⏰ {time_str} | {date_str}"
        )
        return msg


def main():
    bd_tz = timezone(timedelta(hours=6))
    now = datetime.now(bd_tz)
    time_str = now.strftime('%I:%M %p')
    date_str = now.strftime('%d.%m.%y')

    print(f"🔍 Monitor শুরু: {now.strftime('%Y-%m-%d %H:%M')}")

    user_config = load_user_config()
    if not user_config:
        print("   ⚠️ কোনো user config পাওয়া যায়নি!")
        return

    # ─── সব unique keyword কালেক্ট করুন (আলাদাভাবে) ──────
    # cli_cache    → search_in_body=False
    # body_cache   → search_in_body=True
    all_cli_keywords  = set()
    all_body_keywords = set()

    for uid, udata in user_config.items():
        for kw in udata.get('keywords', []):
            all_cli_keywords.add(kw.strip().lower())
        for kw in udata.get('body_keywords', []):
            all_body_keywords.add(kw.strip().lower())

    print(f"   CLI keywords: {len(all_cli_keywords)}")
    print(f"   Body keywords: {len(all_body_keywords)}")

    cli_cache  = {}
    body_cache = {}

    # ─── CLI সার্চ (search_in_body=False) ─────────────────
    for keyword in all_cli_keywords:
        if keyword:
            cli_cache[keyword] = do_search_with_retry(keyword, search_in_body=False)

    # ─── Body সার্চ (search_in_body=True) ─────────────────
    for keyword in all_body_keywords:
        if keyword:
            body_cache[keyword] = do_search_with_retry(keyword, search_in_body=True)

    # ─── Inline keyboard ───────────────────────────────────
    reply_markup = {
        "inline_keyboard": [[
            {"text": "👨‍💻 Developer", "url": "https://t.me/Napa_Ex"},
        ]]
    }

    # ─── প্রতিটি user-কে result পাঠান ────────────────────
    for uid, udata in user_config.items():
        name = udata.get('name', 'User')
        cli_keywords  = [kw.strip().lower() for kw in udata.get('keywords', [])      if kw.strip()]
        body_keywords = [kw.strip().lower() for kw in udata.get('body_keywords', []) if kw.strip()]

        if not cli_keywords and not body_keywords:
            continue

        print(f"\n👤 ইউজার: {name} ({uid})")

        # ── CLI keywords ──
        for keyword in cli_keywords:
            result = cli_cache.get(keyword)
            _send_result(uid, name, keyword, result,
                         time_str, date_str,
                         is_body_search=False,
                         reply_markup=reply_markup)

        # ── Body keywords ──
        for keyword in body_keywords:
            result = body_cache.get(keyword)
            _send_result(uid, name, keyword, result,
                         time_str, date_str,
                         is_body_search=True,
                         reply_markup=reply_markup)

    print("\n✅ সম্পন্ন!")


def _send_result(uid, name, keyword, result,
                 time_str, date_str,
                 is_body_search=False,
                 reply_markup=None):
    """একজন user-কে একটি keyword এর result পাঠান।"""

    search_label = "Body" if is_body_search else "CLI"

    if result == 'captcha':
        send_telegram(uid,
            f"⚠️ <b>reCAPTCHA Block!</b>\n\n"
            f"🔑 Keyword [{search_label}]: <code>{keyword}</code>\n"
            f"⏰ {time_str} | {date_str}"
        )

    elif result == 'error':
        send_telegram(uid,
            f"🔴 <b>Network Error</b>\n\n"
            f"🎯 [{search_label}] <code>{keyword}</code>\n"
            f"━━━━━━━━━━━━━━\n"
            f"সার্ভারে কানেক্ট হয়নি\n"
            f"পরের ৫ মিনিটে আবার চেষ্টা হবে\n\n"
            f"⏰ {time_str} | {date_str}"
        )

    elif result:
        country_lines = ''
        for i, r in enumerate(result, 1):
            flag = get_flag(r)
            country_lines += f"{i}. {r} {flag}\n"

        search_icon = "🔎" if is_body_search else "🌐"
        personal_msg = (
            f"{search_icon}💥 <b>LIVE ALERT</b> 💥{search_icon}\n\n"
            f"{'🔎 Body Search' if is_body_search else '🌐 CLI Search'}\n"
            f"🎯 Keyword » <b>{keyword}</b>\n"
            f"📍 Countries » <b>{len(result)}</b>\n\n"
            f"{country_lines}\n"
            f"⏰ {time_str} | {date_str}"
        )
        send_telegram(uid, personal_msg, reply_markup)

        # Group alert
        ALERT_GROUP_ID = os.environ.get('ALERT_GROUP_ID', '')
        if ALERT_GROUP_ID:
            group_msg = (
                f"👤 <b>{name}</b>\n\n"
                f"{search_icon}💥 <b>LIVE ALERT</b> 💥{search_icon}\n\n"
                f"{'🔎 Body Search' if is_body_search else '🌐 CLI Search'}\n"
                f"🎯 Keyword » <b>{keyword}</b>\n"
                f"📍 Countries » <b>{len(result)}</b>\n\n"
                f"{country_lines}\n"
                f"⏰ {time_str} | {date_str}"
            )
            send_telegram(int(ALERT_GROUP_ID), group_msg)

    else:
        print(f"   ℹ️ [{search_label}] {keyword} → কোনো result নেই")


if __name__ == '__main__':
    main()

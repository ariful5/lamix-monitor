import requests
from bs4 import BeautifulSoup
import os
import re
from datetime import datetime

TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
KEYWORDS         = os.environ.get('SEARCH_KEYWORDS', 'test').split(',')
SEARCH_IN_BODY   = os.environ.get('SEARCH_IN_BODY', 'true').lower() == 'true'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Origin': 'https://lamix.org',
    'Referer': 'https://lamix.org/tools',
}

# ✅ সম্পূর্ণ IGNORE তালিকা — এই শব্দগুলো বা এগুলো ধারণকারী text বাদ দেওয়া হবে
IGNORE_WORDS = {
    'search', 'results', 'cli', 'tools', 'toggle', 'mode', 'submit',
    'loading', 'please', 'wait', 'show', 'hide', 'more', 'less',
    'next', 'prev', 'country', 'countries', 'message', 'body',
    'minute', 'access', 'last', 'find', 'result', 'keyword',
    'lamix', 'sms', 'tool', 'search results', 'cli search',
    'in', 'the', 'from', 'out', 'of', 'a', 'an',
}

# ✅ বিশ্বের সব দেশের নাম — শুধু এগুলোই গ্রহণযোগ্য
VALID_COUNTRIES = {
    "Afghanistan","Albania","Algeria","Andorra","Angola","Argentina","Armenia",
    "Australia","Austria","Azerbaijan","Bahamas","Bahrain","Bangladesh","Belarus",
    "Belgium","Belize","Benin","Bhutan","Bolivia","Bosnia","Botswana","Brazil",
    "Brunei","Bulgaria","Burkina","Burundi","Cambodia","Cameroon","Canada",
    "Chad","Chile","China","Colombia","Comoros","Congo","Croatia","Cuba",
    "Cyprus","Czech","Denmark","Djibouti","Dominican","Ecuador","Egypt",
    "El Salvador","Eritrea","Estonia","Ethiopia","Fiji","Finland","France",
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
    "Tajikistan","Tanzania","Thailand","Togo","Trinidad","Tunisia","Turkey",
    "Turkmenistan","Uganda","Ukraine","United Arab Emirates","United Kingdom",
    "United States","Uruguay","Uzbekistan","Venezuela","Vietnam","Yemen",
    "Zambia","Zimbabwe","Ivory Coast","North Korea","South Korea","New Zealand",
    "Papua New Guinea","Czech Republic","Bosnia and Herzegovina",
    "Trinidad and Tobago","Burkina Faso","Central African Republic",
    "Democratic Republic of Congo","Republic of Congo","Equatorial Guinea",
    "North Macedonia","São Tomé","Cabo Verde","East Timor","Kosovo",
    "UAE", "USA", "UK",
}

# Lowercase সেট — দ্রুত lookup এর জন্য
VALID_COUNTRIES_LOWER = {c.lower() for c in VALID_COUNTRIES}


def search(keyword):
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
        'search_in_body': '1' if SEARCH_IN_BODY else '0',
        'g-recaptcha-response': '',
    }
    if SEARCH_IN_BODY:
        data['toggle_mode'] = 'on'

    resp = session.post('https://lamix.org/tools', data=data, timeout=30)
    resp.raise_for_status()
    return resp.text


def is_valid_country(text):
    """
    একটি text দেশের নাম কিনা যাচাই করে।
    শুধুমাত্র VALID_COUNTRIES তালিকায় থাকা নামই গ্রহণ করে।
    """
    # ইমোজি ও বিশেষ চিহ্ন সরানো
    clean = re.sub(r'[\U0001F000-\U0001FFFF]', '', text).strip()
    # শুধু অক্ষর ও space রাখো
    clean = re.sub(r'[^a-zA-Z\s\-]', '', clean).strip()

    if not clean or len(clean) < 3:
        return None

    # IGNORE_WORDS এ আছে কিনা
    if clean.lower() in IGNORE_WORDS:
        return None

    # VALID_COUNTRIES তালিকায় আছে কিনা (case-insensitive)
    if clean.lower() in VALID_COUNTRIES_LOWER:
        # সঠিক capitalized নাম ফেরত দাও
        for c in VALID_COUNTRIES:
            if c.lower() == clean.lower():
                return c
    return None


def parse_countries(html):
    """
    Lamix সার্চ রেজাল্ট থেকে শুধু দেশের নাম বের করে।
    VALID_COUNTRIES তালিকার বাইরের কিছুই গ্রহণ করে না।
    """
    soup = BeautifulSoup(html, 'html.parser')
    countries = set()

    # ✅ Strategy 1: <li> ট্যাগ — স্ক্রিনশট অনুযায়ী দেশ এখানেই আছে
    for li in soup.find_all('li'):
        # শুধু direct text, nested tag বাদ দাও
        txt = li.get_text(separator=' ', strip=True)
        country = is_valid_country(txt)
        if country:
            countries.add(country)

    # ✅ Strategy 2: class-based elements
    for el in soup.find_all(True, class_=re.compile(r'country|result|item|cli|row|card', re.I)):
        txt = el.get_text(separator=' ', strip=True)
        country = is_valid_country(txt)
        if country:
            countries.add(country)

    # ✅ Strategy 3: fallback — যদি কিছুই না পাওয়া যায়
    if not countries:
        for el in soup.find_all(['td', 'span', 'p']):
            txt = el.get_text(strip=True)
            country = is_valid_country(txt)
            if country:
                countries.add(country)

    return countries


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("   ⚠️  TELEGRAM_TOKEN বা TELEGRAM_CHAT_ID সেট নেই!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }, timeout=15)
        if resp.status_code == 200:
            print("   ✅ Telegram পাঠানো সফল!")
            return True
        else:
            print(f"   ❌ Telegram error: {resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Telegram exception: {e}")
        return False


def main():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    print(f"🔍 Monitor শুরু: {now}")
    print(f"   Keywords: {KEYWORDS}")
    print(f"   Telegram configured: {bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)}")

    for keyword in KEYWORDS:
        keyword = keyword.strip()
        if not keyword:
            continue

        print(f"\n▶ Keyword: '{keyword}'")

        try:
            html = search(keyword)
            print(f"   HTML length: {len(html)} chars")

            # reCAPTCHA চেক
            if 'recaptcha' in html.lower() and len(html) < 2000:
                msg = (
                    f"⚠️ <b>reCAPTCHA Block!</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"🕐 সময়: {now}\n\n"
                    f"Manually check: <a href='https://lamix.org/tools'>lamix.org/tools</a>"
                )
                print("   ⚠️  reCAPTCHA detected!")
                send_telegram(msg)
                continue

            countries = parse_countries(html)
            print(f"   ✅ দেশ পাওয়া: {countries}")

            if countries:
                country_list = '\n'.join(f"• {c}" for c in sorted(countries))
                msg = (
                    f"🚨 <b>Lamix নতুন দেশ পাওয়া গেছে!</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"📊 মোট দেশ: <b>{len(countries)}টি</b>\n\n"
                    f"🌍 দেশসমূহ:\n{country_list}\n\n"
                    f"🕐 সময়: {now}\n"
                    f"🔗 <a href='https://lamix.org/tools'>Lamix দেখুন</a>"
                )
            else:
                msg = (
                    f"🔍 <b>Lamix Search — কোনো দেশ নেই</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"❌ কোনো দেশ পাওয়া যায়নি\n"
                    f"📄 HTML size: {len(html)} chars\n"
                    f"🕐 সময়: {now}\n\n"
                    f"🔗 <a href='https://lamix.org/tools'>Manually দেখুন</a>"
                )

            send_telegram(msg)

        except requests.HTTPError as e:
            err = f"HTTP {e.response.status_code}"
            print(f"   ❌ {err}")
            send_telegram(f"⚠️ <b>HTTP Error</b>\nKeyword: <code>{keyword}</code>\n{err}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            send_telegram(
                f"⚠️ <b>Error</b>\n"
                f"Keyword: <code>{keyword}</code>\n"
                f"{str(e)[:300]}"
            )

    print("\n✅ সম্পন্ন!")


if __name__ == '__main__':
    main()
    token = token_el['value'] if token_el else ''

    # Step 2: POST with search term
    data = {
        '_token': token,
        'search_term': keyword.strip(),
        'search_in_body': '1' if SEARCH_IN_BODY else '0',
        'g-recaptcha-response': '',
    }
    if SEARCH_IN_BODY:
        data['toggle_mode'] = 'on'

    resp = session.post('https://lamix.org/tools', data=data, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_countries(html):
    """
    Extract country names from Lamix search results.
    Tries multiple strategies so nothing is missed.
    """
    soup = BeautifulSoup(html, 'html.parser')
    countries = set()

    # --- Strategy 1: Look for <li> tags (most likely result containers) ---
    for li in soup.find_all('li'):
        txt = li.get_text(strip=True)
        # Strip emoji flags & fire emoji from text
        txt_clean = re.sub(r'[\U0001F300-\U0001FFFF]', '', txt).strip()
        if 2 < len(txt_clean) < 60 and txt_clean not in IGNORE_WORDS:
            if re.match(r'^[A-Z][a-z]+([ \-][A-Z][a-z]+)*$', txt_clean):
                countries.add(txt_clean)

    # --- Strategy 2: Any element with class containing 'country', 'result', 'item' ---
    for el in soup.find_all(True, class_=re.compile(r'country|result|item|cli', re.I)):
        txt = el.get_text(strip=True)
        txt_clean = re.sub(r'[\U0001F300-\U0001FFFF]', '', txt).strip()
        if 2 < len(txt_clean) < 60 and txt_clean not in IGNORE_WORDS:
            if re.match(r'^[A-Z][a-z]+([ \-][A-Z][a-z]+)*$', txt_clean):
                countries.add(txt_clean)

    # --- Strategy 3: Generic fallback — td, span, div, p ---
    if not countries:
        for el in soup.find_all(['td', 'span', 'div', 'p']):
            txt = el.get_text(strip=True)
            txt_clean = re.sub(r'[\U0001F300-\U0001FFFF]', '', txt).strip()
            if 2 < len(txt_clean) < 50 and txt_clean not in IGNORE_WORDS:
                if re.match(r'^[A-Z][a-z]+([ \-][A-Z][a-z]+)*$', txt_clean):
                    countries.add(txt_clean)

    # --- Strategy 4: Unicode flag emoji pairs (bonus info) ---
    full_text = soup.get_text()
    flags = re.findall(r'[\U0001F1E0-\U0001F1FF]{2}', full_text)
    # (flags are kept separate, not mixed into country names)

    return countries, flags


def send_telegram(message):
    """Send a message to Telegram. Returns True on success."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("   ⚠️  TELEGRAM_TOKEN বা TELEGRAM_CHAT_ID সেট নেই!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }, timeout=15)
        if resp.status_code == 200:
            print("   ✅ Telegram পাঠানো সফল!")
            return True
        else:
            print(f"   ❌ Telegram error: {resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ Telegram exception: {e}")
        return False


def main():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    print(f"🔍 Monitor শুরু: {now}")
    print(f"   Keywords: {KEYWORDS}")
    print(f"   Search in body: {SEARCH_IN_BODY}")
    print(f"   Telegram configured: {bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)}")

    for keyword in KEYWORDS:
        keyword = keyword.strip()
        if not keyword:
            continue

        print(f"\n▶ Keyword: '{keyword}'")

        try:
            html = search(keyword)
            print(f"   HTML length: {len(html)} chars")

            # reCAPTCHA check (relaxed — only block if truly tiny)
            if 'recaptcha' in html.lower() and len(html) < 2000:
                msg = (
                    f"⚠️ <b>reCAPTCHA Block!</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"🕐 সময়: {now}\n\n"
                    f"Manually check: <a href='https://lamix.org/tools'>lamix.org/tools</a>"
                )
                print("   ⚠️  reCAPTCHA detected!")
                send_telegram(msg)
                continue

            countries, flags = parse_countries(html)
            print(f"   দেশ পাওয়া: {countries}")
            print(f"   Flag emoji: {flags}")

            if countries:
                country_list = '\n'.join(f"• {c}" for c in sorted(countries))
                flag_str = ' '.join(flags) if flags else ''
                msg = (
                    f"🔍 <b>Lamix CLI Search Result</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"📊 মোট দেশ: <b>{len(countries)}টি</b>\n\n"
                    f"🌍 দেশসমূহ:\n{country_list}\n"
                    + (f"\n🏳️ Flags: {flag_str}\n" if flag_str else '')
                    + f"\n🕐 সময়: {now}\n"
                    f"🔗 <a href='https://lamix.org/tools'>Lamix দেখুন</a>"
                )
            else:
                # Debug: save a snippet of HTML to understand why parsing failed
                snippet = html[:500].replace('<', '&lt;').replace('>', '&gt;')
                msg = (
                    f"🔍 <b>Lamix CLI Search Result</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"❌ কোনো দেশ পাওয়া যায়নি\n"
                    f"📄 HTML size: {len(html)} chars\n"
                    f"🕐 সময়: {now}\n\n"
                    f"🔗 <a href='https://lamix.org/tools'>Manually দেখুন</a>"
                )

            send_telegram(msg)

        except requests.HTTPError as e:
            err_msg = f"HTTP Error {e.response.status_code}"
            print(f"   ❌ {err_msg}")
            send_telegram(f"⚠️ <b>HTTP Error</b>\nKeyword: <code>{keyword}</code>\n{err_msg}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            send_telegram(
                f"⚠️ <b>Error</b>\n"
                f"Keyword: <code>{keyword}</code>\n"
                f"{str(e)[:300]}"
            )

    print("\n✅ সম্পন্ন!")


if __name__ == '__main__':
    main()
        'search_term': keyword.strip(),
        'search_in_body': '1' if SEARCH_IN_BODY else '0',
        'g-recaptcha-response': '',
    }
    if SEARCH_IN_BODY:
        data['toggle_mode'] = 'on'
    resp = session.post('https://lamix.org/tools', data=data, timeout=30)
    return resp.text

def parse_countries(html):
    soup = BeautifulSoup(html, 'html.parser')
    countries = set()
    full_text = soup.get_text()
    flags = re.findall(r'[\U0001F1E0-\U0001F1FF]{2}', full_text)
    countries.update(flags)
    for el in soup.find_all(['td', 'span', 'div', 'p']):
        txt = el.get_text(strip=True)
        if 2 < len(txt) < 50:
            if re.match(r'^[A-Z][a-z]+([ -][A-Z][a-z]+)*$', txt):
                if txt not in IGNORE_WORDS:
                    countries.add(txt)
    return countries

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }, timeout=10)
    return resp.status_code == 200

def main():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    print(f"🔍 Monitor শুরু: {now}")

    for keyword in KEYWORDS:
        keyword = keyword.strip()
        if not keyword:
            continue

        print(f"\n▶ Keyword: '{keyword}'")
        try:
            html = search(keyword)

            if 'recaptcha' in html.lower() and len(html) < 5000:
                send_telegram(f"⚠️ <b>reCAPTCHA block হয়েছে!</b>\nManually check করুন।")
                continue

            countries = parse_countries(html)
            print(f"   পাওয়া: {countries}")

            if countries:
                msg = (
                    f"🔍 <b>Lamix সার্চ রেজাল্ট</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"🌍 দেশ: {', '.join(sorted(countries))}\n"
                    f"📊 মোট: {len(countries)}টি\n"
                    f"🕐 সময়: {now}\n\n"
                    f"🔗 <a href='https://lamix.org/tools'>Lamix দেখুন</a>"
                )
            else:
                msg = (
                    f"🔍 <b>Lamix সার্চ রেজাল্ট</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"❌ কোনো দেশ পাওয়া যায়নি\n"
                    f"🕐 সময়: {now}"
                )

            send_telegram(msg)

        except Exception as e:
            print(f"   ❌ Error: {e}")
            send_telegram(f"⚠️ <b>Error</b>\n{str(e)[:200]}")

    print("\n✅ সম্পন্ন!")

if __name__ == '__main__':
    main()        if 2 < len(txt) < 50:
            if re.match(r'^[A-Z][a-z]+([ -][A-Z][a-z]+)*$', txt):
                if txt not in IGNORE_WORDS:
                    countries.add(txt)

    result_area = None
    for selector in ['#results', '.search-results', '.results']:
        result_area = soup.select_one(selector)
        if result_area:
            break
    if not result_area:
        h3 = soup.find('h3', string=re.compile('Search Results', re.I))
        if h3:
            result_area = h3.find_next_sibling()

    if result_area:
        rows = result_area.find_all(['tr', 'li', 'div'])
        for row in rows:
            row_text = row.get_text(separator=' ', strip=True)
            row_flags = re.findall(r'[\U0001F1E0-\U0001F1FF]{2}', row_text)
            countries.update(row_flags)

    return countries


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram configured নেই")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }, timeout=10)
    print(f"Telegram status: {resp.status_code}")
    return resp.status_code == 200


def load_previous():
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_results(data):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    print(f"🔍 Monitor শুরু: {now}")
    previous = load_previous()
    current = {}

    for keyword in KEYWORDS:
        keyword = keyword.strip()
        if not keyword:
            continue

        print(f"\n▶ Keyword: '{keyword}'")
        try:
            html = search(keyword)

            if 'recaptcha' in html.lower() and 'g-recaptcha' in html.lower() and len(html) < 5000:
                print("⚠️ reCAPTCHA block হয়েছে!")
                send_telegram(f"⚠️ <b>Lamix Monitor</b>\nreCAPTCHA block হয়েছে।")
                continue

            countries = parse_countries(html)
            current[keyword] = list(countries)
            print(f"   পাওয়া দেশ: {countries if countries else 'কোনো দেশ নেই'}")

            prev_countries = set(previous.get(keyword, []))
            new_countries = countries - prev_countries

            if new_countries:
                msg = (
                    f"🚨 <b>Lamix নতুন দেশ পাওয়া গেছে!</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"🌍 নতুন দেশ: {' '.join(new_countries)}\n"
                    f"📊 মোট দেশ: {len(countries)}\n"
                    f"🕐 সময়: {now}\n\n"
                    f"🔗 <a href='https://lamix.org/tools'>Lamix দেখুন</a>"
                )
                send_telegram(msg)
                print(f"   ✅ Notification পাঠানো হয়েছে!")
            else:
                print("   ℹ️ নতুন কোনো দেশ নেই")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            send_telegram(f"⚠️ <b>Error</b>\nKeyword: <code>{keyword}</code>\n{str(e)[:200]}")

    save_results(current)
    print("\n✅ সম্পন্ন!")


if __name__ == '__main__':
    main()            if re.match(r'^[A-Z][a-z]+([ -][A-Z][a-z]+)*$', txt):
                countries.add(txt)

    # Results section খোঁজা
    result_area = None
    for selector in ['#results', '.search-results', '.results']:
        result_area = soup.select_one(selector)
        if result_area:
            break
    if not result_area:
        h3 = soup.find('h3', string=re.compile('Search Results', re.I))
        if h3:
            result_area = h3.find_next_sibling()

    if result_area:
        rows = result_area.find_all(['tr', 'li', 'div'])
        for row in rows:
            row_text = row.get_text(separator=' ', strip=True)
            row_flags = re.findall(r'[\U0001F1E0-\U0001F1FF]{2}', row_text)
            countries.update(row_flags)

    return countries


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram configured নেই")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }, timeout=10)
    print(f"Telegram status: {resp.status_code}")
    return resp.status_code == 200


def load_previous():
    try:
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_results(data):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    print(f"🔍 Monitor শুরু: {now}")
    previous = load_previous()
    current = {}

    for keyword in KEYWORDS:
        keyword = keyword.strip()
        if not keyword:
            continue

        print(f"\n▶ Keyword: '{keyword}'")
        try:
            html = search(keyword)

            # reCAPTCHA block হয়েছে কিনা চেক
            if 'recaptcha' in html.lower() and 'g-recaptcha' in html.lower() and len(html) < 5000:
                print("⚠️ reCAPTCHA block হয়েছে!")
                send_telegram(f"⚠️ <b>Lamix Monitor</b>\nreCAPTCHA block হয়েছে। সাইট manually check করুন।")
                continue

            countries = parse_countries(html)
            current[keyword] = list(countries)
            print(f"   পাওয়া দেশ: {countries if countries else 'কোনো দেশ নেই'}")

            prev_countries = set(previous.get(keyword, []))
            new_countries = countries - prev_countries

            if new_countries:
                msg = (
                    f"🚨 <b>Lamix নতুন দেশ পাওয়া গেছে!</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"🌍 নতুন দেশ: {' '.join(new_countries)}\n"
                    f"📊 মোট দেশ: {len(countries)}\n"
                    f"🕐 সময়: {now}\n\n"
                    f"🔗 <a href='https://lamix.org/tools'>Lamix দেখুন</a>"
                )
                send_telegram(msg)
                print(f"   ✅ Notification পাঠানো হয়েছে!")
            else:
                print("   ℹ️ নতুন কোনো দেশ নেই")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            send_telegram(f"⚠️ <b>Error</b>\nKeyword: <code>{keyword}</code>\n{str(e)[:200]}")

    save_results(current)
    print("\n✅ সম্পন্ন!")


if __name__ == '__main__':
    main()

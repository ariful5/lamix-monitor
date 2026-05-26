import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

# ========== CONFIG ==========
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
KEYWORDS         = os.environ.get('SEARCH_KEYWORDS', 'test').split(',')
RESULTS_FILE     = 'last_results.json'
SEARCH_IN_BODY   = os.environ.get('SEARCH_IN_BODY', 'true').lower() == 'true'
# ============================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Origin': 'https://lamix.org',
    'Referer': 'https://lamix.org/tools',
}

def search(keyword):
    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: GET page → CSRF token নিন
    resp = session.get('https://lamix.org/tools', timeout=30)
    soup = BeautifulSoup(resp.text, 'html.parser')

    token_el = soup.find('input', {'name': '_token'})
    token = token_el['value'] if token_el else ''

    # Step 2: POST করুন
    data = {
        '_token': token,
        'search_term': keyword.strip(),
        'search_in_body': '1' if SEARCH_IN_BODY else '0',
        'g-recaptcha-response': '',
    }
    if SEARCH_IN_BODY:
        data['toggle_mode'] = 'on'

    resp = session.post('https://lamix.org/tools', data=data, timeout=30)
    return resp.text


def parse_countries(html):
    """HTML থেকে দেশের নাম বের করুন"""
    soup = BeautifulSoup(html, 'html.parser')
    countries = set()

    # Flag emoji খোঁজা (🇧🇩 🇺🇸 ইত্যাদি)
    full_text = soup.get_text()
    flags = re.findall(r'[\U0001F1E0-\U0001F1FF]{2}', full_text)
    countries.update(flags)

    # Table বা list এ country নাম খোঁজা
    for el in soup.find_all(['td', 'span', 'div', 'p']):
        txt = el.get_text(strip=True)
        if 2 < len(txt) < 50:
            # সাধারণ country নাম প্যাটার্ন
            if re.match(r'^[A-Z][a-z]+([ -][A-Z][a-z]+)*$', txt):
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

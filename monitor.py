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

# UI শব্দ যেগুলো দেশ না — exact match (lowercase)
IGNORE_EXACT = {
    'search', 'results', 'search results', 'cli', 'cli search',
    'tools', 'toggle', 'mode', 'submit', 'loading', 'please', 'wait',
    'show', 'hide', 'more', 'less', 'next', 'prev',
    'country', 'countries', 'message', 'body', 'minute',
    'access', 'last', 'find', 'result', 'keyword',
    'lamix', 'sms', 'tool', 'in', 'the', 'from', 'out',
    'search in message body', 'find out access from a specific cli in the last 30 minute',
    'lamix cli search tool',
}

# দেশের নাম — operator সহ entry গ্রহণযোগ্য (যেমন "Malaysia - Celcom")
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


def clean_text(txt):
    """ইমোজি ও অপ্রয়োজনীয় চিহ্ন সরিয়ে text পরিষ্কার করো।"""
    # ইমোজি সরাও
    txt = re.sub(r'[\U0001F000-\U0001FFFF]', '', txt)
    # একাধিক space কমাও
    txt = re.sub(r'\s+', ' ', txt)
    return txt.strip()


def is_result_entry(txt):
    """
    একটা text Lamix result entry কিনা যাচাই করো।
    দেশ বা "দেশ - Operator" format হলে True।
    """
    if not txt or len(txt) < 3 or len(txt) > 80:
        return False

    # IGNORE তালিকায় থাকলে বাদ
    if txt.lower() in IGNORE_EXACT:
        return False

    # "Country - Operator" format check
    # যেমন: "Malaysia - Celcom", "Malaysia - Maxis", "Tanzania"
    parts = re.split(r'\s*[-–]\s*', txt, maxsplit=1)
    country_part = parts[0].strip()

    # দেশের নাম VALID_COUNTRIES এ আছে কিনা
    if country_part.lower() in VALID_COUNTRIES_LOWER:
        return True

    return False


def get_canonical(txt):
    """দেশ বা 'দেশ - Operator' এর canonical form ফেরত দাও।"""
    parts = re.split(r'\s*[-–]\s*', txt, maxsplit=1)
    country_part = parts[0].strip()
    canonical_country = VALID_COUNTRIES_LOWER.get(country_part.lower(), country_part)

    if len(parts) > 1:
        operator = parts[1].strip()
        return f"{canonical_country} - {operator}"
    return canonical_country


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


def parse_results(html):
    """
    HTML থেকে সব result entry বের করো।
    দেশ এবং 'দেশ - Operator' উভয়ই গ্রহণ করে।
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    seen = set()

    # Strategy 1: <li> ট্যাগ — স্ক্রিনশট দেখে নিশ্চিত এখানেই data আছে
    for li in soup.find_all('li'):
        txt = clean_text(li.get_text(separator=' ', strip=True))
        if txt and txt.lower() not in seen:
            if is_result_entry(txt):
                canonical = get_canonical(txt)
                if canonical.lower() not in seen:
                    results.append(canonical)
                    seen.add(canonical.lower())

    # Strategy 2: class-based
    if not results:
        for el in soup.find_all(True, class_=re.compile(r'country|result|item|cli|row|card|entry', re.I)):
            # শুধু leaf node (ভেতরে আর tag নেই)
            if not el.find():
                txt = clean_text(el.get_text(strip=True))
                if txt and txt.lower() not in seen:
                    if is_result_entry(txt):
                        canonical = get_canonical(txt)
                        if canonical.lower() not in seen:
                            results.append(canonical)
                            seen.add(canonical.lower())

    # Strategy 3: সব text node থেকে fallback
    if not results:
        for el in soup.find_all(['td', 'span', 'p']):
            if not el.find():
                txt = clean_text(el.get_text(strip=True))
                if txt and txt.lower() not in seen:
                    if is_result_entry(txt):
                        canonical = get_canonical(txt)
                        if canonical.lower() not in seen:
                            results.append(canonical)
                            seen.add(canonical.lower())

    return results


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

            results = parse_results(html)
            print(f"   ✅ Results: {results}")

            if results:
                result_list = '\n'.join(f"• {r}" for r in results)
                msg = (
                    f"🚨 <b>Lamix CLI Search Result</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"📊 মোট: <b>{len(results)}টি</b>\n\n"
                    f"🌍 দেশ / Operator:\n{result_list}\n\n"
                    f"🕐 সময়: {now}\n"
                    f"🔗 <a href='https://lamix.org/tools'>Lamix দেখুন</a>"
                )
            else:
                msg = (
                    f"🔍 <b>Lamix Search</b>\n\n"
                    f"🔑 Keyword: <code>{keyword}</code>\n"
                    f"❌ কোনো result পাওয়া যায়নি\n"
                    f"📄 HTML: {len(html)} chars\n"
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
    

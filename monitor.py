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

IGNORE_WORDS = {
    'Search', 'Results', 'Cli', 'Tools', 'Toggle', 'Mode', 'Submit',
    'Loading', 'Please', 'Wait', 'Show', 'Hide', 'More', 'Less',
    'Next', 'Prev', 'Search Results', 'Cli Search', 'Country', 'Countries',
    'Message', 'Body', 'Minute', 'Access', 'Last', 'Find',
}

def search(keyword):
    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: GET the page to grab CSRF token
    resp = session.get('https://lamix.org/tools', timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    token_el = soup.find('input', {'name': '_token'})
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
    

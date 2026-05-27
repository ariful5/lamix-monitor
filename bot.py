import os
import json
import base64
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# ─── Config ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')
GITHUB_TOKEN   = os.environ.get('GITHUB_PAT', '')
GITHUB_REPO    = os.environ.get('GITHUB_REPO', 'ariful5/lamix-monitor')
ADMIN_IDS      = [x.strip() for x in os.environ.get('ADMIN_IDS', '').split(',') if x.strip()]
CONFIG_FILE    = 'users_config.json'

GH_HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# ─── GitHub Storage ────────────────────────────────────────
def load_config():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_FILE}"
    r = requests.get(url, headers=GH_HEADERS, timeout=10)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data['content']).decode()
        return json.loads(content), data['sha']
    return {}, None

def save_config(config, sha=None):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONFIG_FILE}"
    content = base64.b64encode(
        json.dumps(config, indent=2, ensure_ascii=False).encode()
    ).decode()
    body = {'message': '🔧 Update user config', 'content': content}
    if sha:
        body['sha'] = sha
    r = requests.put(url, headers=GH_HEADERS, json=body, timeout=10)
    return r.status_code in [200, 201]

# ─── Helpers ───────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Keyword যোগ করুন", callback_data="help_add")],
        [InlineKeyboardButton("📋 আমার Keywords", callback_data="my_list"),
         InlineKeyboardButton("🗑 Keyword মুছুন", callback_data="help_remove")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/Napa_Ex")],
    ])

# ─── /start ───────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "বন্ধু"

    config, sha = load_config()
    uid = str(user.id)
    if uid not in config:
        config[uid] = {"name": name, "keywords": []}
        save_config(config, sha)

    text = (
        f"👋 স্বাগতম, <b>{name}</b>!\n\n"
        f"🤖 <b>Lamix Alert Bot</b> — আপনার ব্যক্তিগত SMS মনিটর\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>কী করে এই বট?</b>\n"
        f"প্রতি ৫ মিনিটে Lamix.org চেক করে, আপনার কীওয়ার্ড খুঁজে পেলে সাথে সাথে অ্যালার্ট পাঠায়।\n\n"
        f"⚙️ <b>কমান্ড লিস্ট:</b>\n"
        f"▶ /add keyword — নতুন keyword যোগ করুন\n"
        f"▶ /remove keyword — keyword মুছুন\n"
        f"▶ /list — আপনার সব keyword দেখুন\n"
        f"▶ /help — সাহায্য\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>উদাহরণ:</b>\n"
        f"<code>/add mywebsite.com</code>\n"
        f"<code>/remove mywebsite.com</code>\n"
    )
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_keyboard())

# ─── /help ────────────────────────────────────────────────
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>Help — Lamix Alert Bot</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 <b>/add</b> <code>keyword</code>\n"
        "   নতুন website/keyword মনিটর করতে যোগ করুন\n"
        "   উদাহরণ: <code>/add example.com</code>\n\n"
        "🔹 <b>/remove</b> <code>keyword</code>\n"
        "   keyword মনিটর বন্ধ করতে মুছুন\n"
        "   উদাহরণ: <code>/remove example.com</code>\n\n"
        "🔹 <b>/list</b>\n"
        "   আপনার সব active keyword দেখুন\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ প্রতিটা ইউজারের keyword আলাদা।\n"
        "শুধু আপনার keyword-এর result আপনি পাবেন।"
    )
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_keyboard())

# ─── /add ─────────────────────────────────────────────────
async def add_keyword(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)

    if not ctx.args:
        await update.message.reply_text(
            "⚠️ Keyword লিখুন!\n\nউদাহরণ: <code>/add example.com</code>",
            parse_mode='HTML'
        )
        return

    keyword = ' '.join(ctx.args).strip().lower()
    config, sha = load_config()

    if uid not in config:
        config[uid] = {"name": user.first_name or "User", "keywords": []}

    if keyword in config[uid]['keywords']:
        await update.message.reply_text(
            f"⚠️ <b>{keyword}</b> আগে থেকেই আছে!\n\n"
            f"📋 আপনার keywords দেখতে: /list",
            parse_mode='HTML'
        )
        return

    if len(config[uid]['keywords']) >= 10:
        await update.message.reply_text(
            "❌ সর্বোচ্চ <b>১০টা</b> keyword রাখা যাবে।\n"
            "আগে /remove দিয়ে কিছু মুছুন।",
            parse_mode='HTML'
        )
        return

    config[uid]['keywords'].append(keyword)
    if save_config(config, sha):
        count = len(config[uid]['keywords'])
        await update.message.reply_text(
            f"✅ <b>{keyword}</b> যোগ হয়েছে!\n\n"
            f"📊 মোট keywords: <b>{count}</b>\n"
            f"⏱ পরের ৫ মিনিটের মধ্যে মনিটরিং শুরু হবে।",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("❌ সংরক্ষণ করতে পারিনি। আবার চেষ্টা করুন।")

# ─── /remove ──────────────────────────────────────────────
async def remove_keyword(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)

    if not ctx.args:
        await update.message.reply_text(
            "⚠️ Keyword লিখুন!\n\nউদাহরণ: <code>/remove example.com</code>",
            parse_mode='HTML'
        )
        return

    keyword = ' '.join(ctx.args).strip().lower()
    config, sha = load_config()

    if uid not in config or keyword not in config[uid].get('keywords', []):
        await update.message.reply_text(
            f"❌ <b>{keyword}</b> আপনার list-এ নেই!\n\n"
            f"📋 আপনার keywords: /list",
            parse_mode='HTML'
        )
        return

    config[uid]['keywords'].remove(keyword)
    if save_config(config, sha):
        await update.message.reply_text(
            f"🗑 <b>{keyword}</b> সরানো হয়েছে!\n\n"
            f"📊 বাকি keywords: <b>{len(config[uid]['keywords'])}</b>",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("❌ সংরক্ষণ করতে পারিনি। আবার চেষ্টা করুন।")

# ─── /list ────────────────────────────────────────────────
async def list_keywords(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    config, _ = load_config()

    keywords = config.get(uid, {}).get('keywords', [])
    if not keywords:
        await update.message.reply_text(
            "📋 আপনার কোনো keyword নেই।\n\n"
            "যোগ করতে: <code>/add example.com</code>",
            parse_mode='HTML'
        )
        return

    lines = '\n'.join([f"  {i+1}. <code>{kw}</code>" for i, kw in enumerate(keywords)])
    await update.message.reply_text(
        f"📋 <b>আপনার Keywords ({len(keywords)}/10)</b>\n\n"
        f"{lines}\n\n"
        f"➕ যোগ: <code>/add keyword</code>\n"
        f"🗑 মুছুন: <code>/remove keyword</code>",
        parse_mode='HTML'
    )

# ─── Callback ─────────────────────────────────────────────
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "my_list":
        update._effective_message = query.message
        update._effective_user = query.from_user
        await list_keywords(update, ctx)
    elif query.data == "help_add":
        await query.message.reply_text(
            "➕ Keyword যোগ করতে লিখুন:\n\n<code>/add example.com</code>",
            parse_mode='HTML'
        )
    elif query.data == "help_remove":
        await query.message.reply_text(
            "🗑 Keyword মুছতে লিখুন:\n\n<code>/remove example.com</code>",
            parse_mode='HTML'
        )

# ─── Main ─────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_keyword))
    app.add_handler(CommandHandler("remove", remove_keyword))
    app.add_handler(CommandHandler("list", list_keywords))
    app.add_handler(CallbackQueryHandler(callback_handler))
    print("🤖 Bot চালু হয়েছে...")
    app.run_polling()

if __name__ == '__main__':
    main()
  

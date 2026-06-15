import requests
import os
import asyncio
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

print("Starting bot v2...", flush=True)
HEADERS = {"User-Agent": "Mozilla/5.0"}
BOT_TOKEN = os.environ.get("BOT_TOKEN")

def get_countries():
    res = requests.get("https://quackr.io/temporary-numbers", headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    countries = []
    seen = set()
    for a in soup.select("a[href*='/temporary-numbers/']"):
        href = a.get("href", "")
        name = a.get_text(strip=True)
        code = href.split("/temporary-numbers/")[-1].strip("/")
        if code and name and len(name) > 1 and not name.startswith("+") and code not in seen:
            seen.add(code)
            countries.append({"country": name, "code": code})
    return countries

def get_numbers_for_country(country_code):
    url = f"https://quackr.io/temporary-numbers/{country_code}"
    res = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    numbers = []
    for a in soup.select("a[href*='/temporary-numbers/']"):
        text = a.get_text(strip=True)
        if text.startswith("+"):
            numbers.append({"number": text})
    return numbers


def get_messages(number):
    clean = number.replace("+", "").replace(" ", "")
    url = f"https://quackr.io/temporary-numbers/{clean}"
    res = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    messages = []
    for row in soup.select("table tr"):
        cols = row.find_all("td")
        if len(cols) >= 3:
            messages.append({
                "sender": cols[0].get_text(strip=True),
                "message": cols[1].get_text(strip=True),
                "time": cols[2].get_text(strip=True),
            })
    return messages


async def list_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Fetching numbers, please wait...")
    try:
        data = get_countries()
        if not data:
            await update.message.reply_text("No countries found. Try again.")
            return
        keyboard = []
        for country in data[:10]:
            name = country.get("country", "Unknown")
            code = country.get("code", "")
            keyboard.append([InlineKeyboardButton(name, callback_data=f"country:{code}")])
        await update.message.reply_text("Select a country:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def country_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    country_code = query.data.split(":")[1]
    try:
        numbers = get_numbers_for_country(country_code)
        if not numbers:
            await query.edit_message_text("No numbers found for this country.")
            return
        keyboard = []
        for num in numbers[:8]:
            n = num.get("number", "")
            keyboard.append([InlineKeyboardButton(n, callback_data=f"select:{n}")])
        await query.edit_message_text("Select a number:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = context.user_data.get("selected_number")
    if not number:
        await update.message.reply_text("No number selected. Use /numbers first.")
        return
    await update.message.reply_text(f"Checking SMS for {number}...")
    try:
        messages = get_messages(number)
        if not messages:
            await update.message.reply_text("No messages yet. Try again soon.")
        else:
            reply = f"Messages for {number}:\n\n"
            for msg in messages[:5]:
                reply += f"From: {msg.get('sender','')}\nMsg: {msg.get('message','')}\nTime: {msg.get('time','')}\n\n"
            await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def watch_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = context.user_data.get("selected_number")
    if not number:
        await update.message.reply_text("Select a number first with /numbers.")
        return
    await update.message.reply_text(f"Watching {number} for 2 minutes...")
    seen = set()
    for _ in range(24):
        await asyncio.sleep(5)
        try:
            messages = get_messages(number)
            for msg in messages:
                key = (msg.get("sender"), msg.get("time"))
                if key not in seen:
                    seen.add(key)
                    await update.message.reply_text(f"New SMS!\nFrom: {msg.get('sender')}\n{msg.get('message')}")
                    return
        except:
            pass
    await update.message.reply_text("Timeout. No messages received.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Temp Number Bot\n\n"
        "/numbers - List numbers\n"
        "/getcode - Check SMS\n"
        "/mynumber - Your number\n"
        "/watch - Auto watch SMS"
    )

async def number_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    number = query.data.split(":")[1]
    context.user_data["selected_number"] = number
    await query.edit_message_text(f"Selected: {number}\n\nUse it for verification then send /getcode")

async def my_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = context.user_data.get("selected_number")
    if number:
        await update.message.reply_text(f"Your number: {number}")
    else:
        await update.message.reply_text("No number selected. Use /numbers.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("numbers", list_numbers))
    app.add_handler(CommandHandler("getcode", get_code))
    app.add_handler(CommandHandler("mynumber", my_number))
    app.add_handler(CommandHandler("watch", watch_code))
    app.add_handler(CallbackQueryHandler(country_selected, pattern="^country:"))
    app.add_handler(CallbackQueryHandler(number_selected, pattern="^select:"))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception as e:
        print(f"CRASH: {e}")
        traceback.print_exc()
# updated

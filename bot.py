import requests
import os
import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.environ.get("8827534972:AAEY5Ov0dc4AjbgaMbiDv1J3Llbtabx-33A")

async def get_countries():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://quackr.io/temporary-numbers", wait_until="networkidle")
        links = await page.query_selector_all("a[href*='/temporary-numbers/']")
        countries = []
        seen = set()
        for a in links:
            href = await a.get_attribute("href") or ""
            name = (await a.inner_text()).strip()
            code = href.split("/temporary-numbers/")[-1].strip("/")
            if code and name and not name.startswith("+") and code not in seen:
                seen.add(code)
                countries.append({"country": name, "code": code})
        await browser.close()
        return countries

async def get_numbers_for_country(country_code):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"https://quackr.io/temporary-numbers/{country_code}", wait_until="networkidle")
        links = await page.query_selector_all("a[href*='/temporary-numbers/']")
        numbers = []
        for a in links:
            text = (await a.inner_text()).strip()
            href = await a.get_attribute("href") or ""
            if text.startswith("+"):
                numbers.append({"number": text, "href": href})
        await browser.close()
        return numbers


async def get_messages(number):
    clean = number.replace("+", "").replace(" ", "")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"https://quackr.io/temporary-numbers/{clean}", wait_until="networkidle")
        rows = await page.query_selector_all("table tr")
        messages = []
        for row in rows:
            cols = await row.query_selector_all("td")
            if len(cols) >= 3:
                messages.append({
                    "sender": (await cols[0].inner_text()).strip(),
                    "message": (await cols[1].inner_text()).strip(),
                    "time": (await cols[2].inner_text()).strip(),
                })
        await browser.close()
        return messages

async def list_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Fetching numbers, please wait...")
    try:
        data = await get_countries()
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
        numbers = await get_numbers_for_country(country_code)
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
        messages = await get_messages(number)
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
            messages = await get_messages(number)
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

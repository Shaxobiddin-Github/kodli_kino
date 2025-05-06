import logging
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ApplicationBuilder
from telegram.error import NetworkError
from github import Github
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web, ClientSession
import asyncio
from telegram.ext import ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHANNELS = [
    {"username": "@uz_film_zone", "name": "Kodli Kinolar"},
]

# GitHub sozlamalari
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN muhit o'zgaruvchisi topilmadi!")

REPO_NAME = "Shaxobiddin-Github/kodli_kinolar"
FILE_PATH = "video_map.json"

# GitHub'dan faylni o'qish
def load_video_data():
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        logger.info(f"Attempting to read {FILE_PATH} from {REPO_NAME}")
        file_content = repo.get_contents(FILE_PATH)
        data = json.loads(base64.b64decode(file_content.content).decode("utf-8"))
        logger.info(f"Successfully loaded data from {FILE_PATH}: {data}")
        return {k: tuple(v) for k, v in data.items()}
    except Exception as e:
        logger.error(f"GitHub'dan fayl o'qishda xato: {e}")
        return {}

# GitHub'ga faylni saqlash
def save_video_data(data):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        logger.info(f"Attempting to save data to {FILE_PATH}: {data}")
        try:
            file_content = repo.get_contents(FILE_PATH)
            repo.update_file(
                FILE_PATH,
                "Update video_map.json",
                json.dumps(data, ensure_ascii=False),
                file_content.sha
            )
            logger.info(f"Successfully updated {FILE_PATH}")
        except:
            repo.create_file(
                FILE_PATH,
                "Create video_map.json",
                json.dumps(data, ensure_ascii=False)
            )
            logger.info(f"Successfully created {FILE_PATH}")
    except Exception as e:
        logger.error(f"GitHub'ga fayl saqlashda xato: {e}")
        raise

hashtag_to_video = load_video_data()

# Vaqtincha hashtaglarni saqlaymiz
user_last_hashtag = {}

# TOKEN va Webhook URL ni muhit o'zgaruvchisidan olish
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN muhit o'zgaruvchisi topilmadi!")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL muhit o'zgaruvchisi topilmadi!")

# Application ni yaratish
application = ApplicationBuilder().token(TOKEN).build()

# Kanalga kelgan xabarlar
async def channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message:
        return

    user_id = message.chat_id
    text = message.text
    video = message.video

    if text and text.startswith("#"):
        user_last_hashtag[user_id] = text.strip()
        logger.info(f"Hashtag xabari qabul qilindi: {text.strip()}")

    elif video:
        hashtag = user_last_hashtag.get(user_id)
        if not hashtag:
            logger.info("Video keldi, lekin hashtag topilmadi.")
            return

        clean_hashtag = hashtag.lstrip("#")
        hashtag_to_video[clean_hashtag] = (message.chat_id, message.message_id)
        logger.info(f"Video va hashtag topildi: hashtag={clean_hashtag}, video_id={message.message_id}")

        # GitHub'ga saqlash
        save_video_data(hashtag_to_video)

    else:
        logger.info("Xabar hashtag yoki video emas.")





# Botga shaxsiy yozilgan xabarlar
async def private_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    user_chat_id = message.chat_id

    logger.info(f"Foydalanuvchi yubordi: {text}")

    if text in hashtag_to_video:
        video_chat_id, video_msg_id = hashtag_to_video[text]
        # Video yuborish
        await context.bot.copy_message(
            chat_id=user_chat_id,
            from_chat_id=video_chat_id,
            message_id=video_msg_id
        )
        # Kanal nomi bilan video pastiga qo'shish
        await context.bot.send_message(
            chat_id=user_chat_id,
            text=f"Kanal: [Kodli Kinolar](https://t.me/kodli_kinolar_1234)",
            parse_mode="Markdown"
        )
        logger.info(f"{text} uchun video yuborildi.")
    else:
        await message.reply_text("Kechirasiz, bu kod uchun video topilmadi.")
        logger.info("Video topilmadi.")

# Start komandasi (test uchun)from telegram import Update
from telegram.error import NetworkError, TelegramError

# Foydalanuvchining kanal a'zoligini tekshirish
async def check_channel_membership(bot, user_id: int, channel_username: str) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.error(f"Kanal {channel_username} a'zoligini tekshirishda xato: {e}")
        return False

# Barcha kanallarga a'zolikni tekshirish
async def check_all_channels(bot, user_id: int) -> list:
    non_member_channels = []
    for channel in CHANNELS:
        is_member = await check_channel_membership(bot, user_id, channel["username"])
        if not is_member:
            non_member_channels.append(channel)
    return non_member_channels

# Kanallar ro'yxatini buttonlar bilan ko'rsatish
def create_channels_keyboard(non_member_channels: list) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(channel["name"], url=f"https://t.me/{channel['username'].lstrip('@')}")]
        for channel in non_member_channels
    ]
    return InlineKeyboardMarkup(keyboard)

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_chat_id = update.effective_chat.id

    # Barcha kanallarga a'zolikni tekshirish
    non_member_channels = await check_all_channels(context.bot, user_id)

    if non_member_channels:
        # Agar foydalanuvchi barcha kanallarga a'zo bo'lmasa
        text = (
            "🎬 *Assalomu alaykum!*\n\n"
            "Botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling:\n\n"
            "A'zo bo'lgandan so'ng, qayta `/start` buyrug'ini yuboring. ✅"
        )
        reply_markup = create_channels_keyboard(non_member_channels)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
        logger.info(f"Foydalanuvchi {user_id} ba'zi kanallarga a'zo emas: {[ch['username'] for ch in non_member_channels]}")
        return

    # Agar foydalanuvchi barcha kanallarga a'zo bo'lsa
    text = (
        "🎬 *Assalomu alaykum!*\n\n"
        "Bu bot yordamida siz *film kodi* orqali filmni topishingiz mumkin. 🎥\n"
        "Bot sizga film haqida ma'lumot, treyler va *Instagram havolasini* yuboradi. 📱\n\n"
        "📌 *Rasmiy Telegram kanalimiz:* [Kodli Kinolar](https://t.me/uz_film_zone)\n"
        "📸 *Instagram sahifamiz:* [@uz_film_zone](https://www.instagram.com/uz_film_zone)\n\n"
        "Film topish uchun kod yuboring yoki /help buyrug‘idan foydalaning. ✅"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    logger.info(f"Foydalanuvchi {user_id} barcha kanallarga a'zo, start xabari yuborildi.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ *Yordam bo‘limi*\n\n"
        "🔹 *Botdan foydalanish bo‘yicha ko‘rsatmalar:*\n"
        "1. Film kodini yuboring (masalan: `1234`).\n"
        "2. Bot sizga filmning videosini, tavsifini va Instagram havolasini yuboradi.\n"
        "3. Agar sizda kod bo‘lmasa, uni rasmiy kanalimizdan topishingiz mumkin.\n\n"
        "📌 *Telegram kanalimiz:* [Kodli Kinolar](https://t.me/kodli_kinolar_1234)\n"
        "📸 *Instagram sahifamiz:* [@uz_film_zone](https://www.instagram.com/uz_film_zone)\n\n"
        "Agar savollaringiz bo‘lsa, biz bilan bog‘laning. ✅"
    )

    await update.message.reply_text(text, parse_mode="Markdown")



# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xato yuz berdi: {context.error}")
    if isinstance(context.error, NetworkError):
        logger.warning("Tarmoq xatosi aniqlandi, qayta urinish mumkin.")
        if update and update.message:
            await update.message.reply_text("Tarmoq xatosi yuz berdi, iltimos qayta urinib ko‘ring.")
    else:
        if update and update.message:
            await update.message.reply_text("Xato yuz berdi, iltimos keyinroq qayta urinib ko‘ring.")

# Avval komandalarni qo‘shish
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))

# Keyin kanal va shaxsiy xabarlar
application.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_handler))
application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, private_handler))

# Xatoliklar uchun
application.add_error_handler(error_handler)


# Webhook server
async def webhook(request):
    try:
        update = await request.json()
        if not update:
            logger.warning("Received empty update from Telegram")
            return web.Response(text="No update received", status=400)
        update_obj = Update.de_json(update, application.bot)
        if update_obj is None:
            logger.warning("Failed to parse update from Telegram")
            return web.Response(text="Invalid update", status=400)
        await application.process_update(update_obj)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        return web.Response(text="Internal Server Error", status=500)

# Keep-alive uchun GET endpoint
async def keepalive(request):
    logger.info("Keep-alive request received")
    return web.Response(text="OK")

# Keep-alive funksiyasi
async def keep_alive():
    webhook_url = f"{WEBHOOK_URL}/{TOKEN}"
    async with ClientSession() as session:
        while True:
            try:
                async with session.post(webhook_url, json={}) as response:
                    logger.info(f"Keep-alive request sent, status: {response.status}")
            except Exception as e:
                logger.error(f"Keep-alive request failed: {e}")
            await asyncio.sleep(600)  # Har 10 daqiqada (600 soniya) so‘rov yuborish

# Aiohttp serverini sozlash
app = web.Application()

# Event loop va serverni to‘g‘ri yopish uchun cleanup
async def shutdown_app(app):
    logger.info("Shutting down application...")
    await application.stop()
    await application.shutdown()
    logger.info("Application stopped.")

app.on_shutdown.append(shutdown_app)
app.router.add_post(f"/{TOKEN}", webhook)
app.router.add_get("/keepalive", keepalive)

# Webhook'ni o'rnatish va Application ni ishga tushirish
async def setup_application():
    # Application ni initialize qilish
    await application.initialize()
    logger.info("Application initialized")

    application.add_handler(CommandHandler("help", help_command))

    # Webhook'ni o'rnatish
    webhook_url = f"{WEBHOOK_URL}/{TOKEN}"
    await application.bot.setWebhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

    # Application ni ishga tushirish
    await application.start()
    logger.info("Application started")

# Serverni ishga tushirish
if __name__ == "__main__":
    # Yangi event loop yaratish
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Setup qilish
    loop.run_until_complete(setup_application())
    
    # Keep-alive vazifasini ishga tushirish
    loop.create_task(keep_alive())
    
    # Serverni ishga tushirish
    port = int(os.getenv("PORT", 8000))  # Render PORT ni muhit o'zgaruvchisidan oladi, default 8000
    logger.info(f"Starting server on port {port}")
    try:
        web.run_app(app, host="0.0.0.0", port=port, loop=loop)
    finally:
        loop.close()
        logger.info("Event loop closed.")
import os
import re
import tempfile
import shutil
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import yt_dlp

BOT_TOKEN = os.environ["BOT_TOKEN"]

def clean_caption(text: str):
    if not text:
        return ""
    text = re.sub(r"#\w+", "", text)   # remove hashtags
    text = re.sub(r"@\w+", "", text)   # remove mentions
    return text.strip()

def extract_audio(video_path, out_path):
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-ab", "192k",
        out_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if "instagram.com" not in text:
        return

    chat_id = update.effective_chat.id
    await update.message.reply_text("⏳ Fetching...")

    temp_dir = tempfile.mkdtemp()

    try:
        ydl_opts = {
            "outtmpl": f"{temp_dir}/%(title)s.%(ext)s",
            "format": "best[height<=720]/best",
            "quiet": True,
            "no_warnings": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(text, download=True)

        files = os.listdir(temp_dir)
        video_file = next(f for f in files if f.endswith((".mp4", ".webm", ".mkv")))
        video_path = os.path.join(temp_dir, video_file)

        caption = clean_caption(info.get("description", ""))
        username = info.get("uploader", "unknown")
        song = info.get("track", "Unknown")

        final_caption = f"@{username}\n🎵 Song: {song}\n🔗 Source: {text}\n\n{caption}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 Download Audio", callback_data="audio")]
        ])

        msg = await ctx.bot.send_video(chat_id, video=open(video_path, "rb"), caption=final_caption, reply_markup=keyboard)

        ctx.chat_data[msg.message_id] = video_path

    except:
        await update.message.reply_text("❌ Failed to fetch media.")
        shutil.rmtree(temp_dir, ignore_errors=True)

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    video_path = ctx.chat_data.get(query.message.message_id)
    if not video_path:
        await query.message.reply_text("❌ File expired.")
        return

    audio_path = video_path + ".mp3"
    extract_audio(video_path, audio_path)

    await query.message.reply_audio(audio=open(audio_path, "rb"))

    shutil.rmtree(os.path.dirname(video_path), ignore_errors=True)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(filters.CallbackQueryHandler(button_handler))

app.run_polling()

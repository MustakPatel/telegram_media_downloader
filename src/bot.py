import os
import sys
import time
import re
import requests

# Ensure root folder is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.downloader import extract_media_info, download_video, download_audio, cleanup_file

DEFAULT_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8993271292:AAFqmVh6MdUHMpyvOULWnAWP27qedY6L6PM")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8530348020")

URL_REGEX = re.compile(r'https?://[^\s]+')

def send_telegram_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Helper to send HTML formatted text message to Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram text message: {e}")
        return False

def send_telegram_video(token: str, chat_id: str, filepath: str, caption: str = "") -> bool:
    """Uploads video file directly to Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    try:
        with open(filepath, 'rb') as vf:
            files = {'video': vf}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            r = requests.post(url, data=data, files=files, timeout=120)
            return r.status_code == 200
    except Exception as e:
        print(f"Error uploading video to Telegram: {e}")
        return False

def send_telegram_audio(token: str, chat_id: str, filepath: str, caption: str = "") -> bool:
    """Uploads MP3 audio file directly to Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendAudio"
    try:
        with open(filepath, 'rb') as af:
            files = {'audio': af}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            r = requests.post(url, data=data, files=files, timeout=120)
            return r.status_code == 200
    except Exception as e:
        print(f"Error uploading audio to Telegram: {e}")
        return False

def process_command_or_link(text: str, chat_id: str, token: str):
    """Processes incoming mobile text, commands, or pasted video links."""
    text_strip = text.strip()
    parts = text_strip.split()
    cmd = parts[0].lower() if parts else ""

    if cmd in ["/start", "/help"]:
        msg = """
🤖 <b>UNIVERSAL MEDIA & VIDEO DOWNLOADER BOT</b> 🤖

📲 <b>How to Use:</b>
1. <b>Direct Download Video:</b> Simply paste ANY video link in chat (YouTube, Instagram Reel, Twitter, TikTok, HLS stream, etc.).
2. <b>Extract MP3 Audio:</b> Type <code>/audio &lt;link&gt;</code> or <code>/mp3 &lt;link&gt;</code>.
3. <b>Check Media Info:</b> Type <code>/info &lt;link&gt;</code>.

⚡ <b>Features:</b>
• 100% Ad-Free HD Video Downloads (1080p MP4)
• Audio MP3 Conversion
• Supports 1,800+ sites & HLS/m3u8 Streams
"""
        send_telegram_message(token, chat_id, msg.strip())
        return

    # Handle /info command
    if cmd == "/info" and len(parts) > 1:
        target_url = parts[1]
        send_telegram_message(token, chat_id, "🔍 Extracting media info from URL...")
        info = extract_media_info(target_url)
        if info["status"] == "success":
            msg = f"""
ℹ️ <b>MEDIA INFO REPORT</b> ℹ️

📌 <b>Title:</b> {info['title']}
👤 <b>Uploader / Platform:</b> {info['uploader']}
⏱️ <b>Duration:</b> {info['duration']}
💾 <b>Est. Size:</b> ~{info['filesize_mb']} MB
🔗 <b>URL:</b> {info['url']}
"""
            send_telegram_message(token, chat_id, msg.strip())
        else:
            send_telegram_message(token, chat_id, f"⚠️ Error: {info.get('message', 'Failed to extract info.')}")
        return

    # Handle /audio or /mp3 command
    if cmd in ["/audio", "/mp3"] and len(parts) > 1:
        target_url = parts[1]
        send_telegram_message(token, chat_id, "🎵 Extracting high-quality MP3 audio... Please wait.")
        res = download_audio(target_url)
        if res["status"] == "success":
            caption = f"🎵 <b>{res['title']}</b>\n💾 Size: {res['filesize_mb']} MB"
            send_telegram_message(token, chat_id, "📤 Uploading MP3 to Telegram...")
            uploaded = send_telegram_audio(token, chat_id, res["filepath"], caption=caption)
            if not uploaded:
                send_telegram_message(token, chat_id, f"⚠️ File size ({res['filesize_mb']} MB) exceeds Telegram 50MB direct bot upload limit.")
            cleanup_file(res["filepath"])
        else:
            send_telegram_message(token, chat_id, f"⚠️ Audio download failed: {res.get('message')}")
        return

    # Handle direct URL paste
    urls = URL_REGEX.findall(text_strip)
    if urls:
        target_url = urls[0]
        send_telegram_message(token, chat_id, "📥 Processing & Downloading HD Video... Please wait.")
        res = download_video(target_url)
        if res["status"] == "success":
            caption = f"🎬 <b>{res['title']}</b>\n💾 Size: {res['filesize_mb']} MB"
            send_telegram_message(token, chat_id, "📤 Uploading Video to Telegram...")
            uploaded = send_telegram_video(token, chat_id, res["filepath"], caption=caption)
            if not uploaded:
                send_telegram_message(token, chat_id, f"⚠️ File size ({res['filesize_mb']} MB) exceeds Telegram 50MB direct bot upload limit.")
            cleanup_file(res["filepath"])
        else:
            send_telegram_message(token, chat_id, f"⚠️ Video download failed: {res.get('message')}")
        return

    send_telegram_message(token, chat_id, "Unknown command or link. Type /help to see usage instructions.")

def start_bot_loop(token: str = DEFAULT_BOT_TOKEN):
    """Starts the long-polling Telegram Bot worker."""
    if not token:
        print("Telegram bot token required. Worker idle.")
        return
        
    url = f"https://api.telegram.org/bot{token.strip()}"
    last_update_id = 0
    print(f"🤖 Starting Universal Media Downloader Bot Worker...")

    while True:
        try:
            resp = requests.get(f"{url}/getUpdates?offset={last_update_id + 1}&timeout=10", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    text = message.get("text", "")
                    sender_chat_id = str(message.get("chat", {}).get("id", ""))

                    if text and sender_chat_id:
                        print(f"Received link/command: '{text}' from Chat ID: {sender_chat_id}")
                        process_command_or_link(text, sender_chat_id, token)
        except Exception as e:
            print(f"Telegram long-polling error: {e}")
        time.sleep(2)

if __name__ == "__main__":
    start_bot_loop()

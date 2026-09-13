import os
import sys
import time
import re
import urllib.parse
import requests

# Ensure root folder and current working directory are in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath("."))

try:
    from src.downloader import extract_media_info, download_video, download_audio, split_video, cleanup_file
    from src.server import start_download_server
except ModuleNotFoundError:
    from downloader import extract_media_info, download_video, download_audio, split_video, cleanup_file
    from server import start_download_server

DEFAULT_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8862252811:AAEdkDx0sXYTySvVMiN7jiCUsTqCPOpvNj8")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8530348020")
SERVER_PORT = int(os.environ.get("PORT", "10000"))

URL_REGEX = re.compile(r'https?://[^\s]+')

def get_public_download_url(filename: str) -> str:
    """Generates direct download URL for files served via Flask download server."""
    quoted = urllib.parse.quote(filename)
    return f"http://localhost:{SERVER_PORT}/download/{quoted}"

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
            r = requests.post(url, data=data, files=files, timeout=300)
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
            r = requests.post(url, data=data, files=files, timeout=300)
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
• Handles ANY File Size (Splits >50MB files into video parts)
• Audio MP3 Extraction
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
                send_telegram_message(token, chat_id, f"⚠️ Audio size ({res['filesize_mb']} MB) exceeds Telegram limit.")
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
            orig_filepath = res["filepath"]
            orig_size_mb = res["filesize_mb"]
            title = res["title"]

            # If file fits in 1 single Telegram video upload (<= 45MB)
            if orig_size_mb <= 45.0:
                caption = f"🎬 <b>{title}</b>\n💾 Size: {orig_size_mb} MB"
                send_telegram_message(token, chat_id, "📤 Uploading HD Video to Telegram...")
                send_telegram_video(token, chat_id, orig_filepath, caption=caption)
                cleanup_file(orig_filepath)
            else:
                # File is > 45MB (e.g. 92MB, 500MB, 1GB). Split into 40MB playable parts!
                send_telegram_message(token, chat_id, f"⚡ <b>Large Video File Detected ({orig_size_mb:.1f} MB)</b>\n✂️ Splitting into playable HD video parts for Telegram upload...")
                parts_list = split_video(orig_filepath, max_part_size_mb=40.0)

                for idx, part_path in enumerate(parts_list, start=1):
                    part_size = round(os.path.getsize(part_path) / (1024 * 1024), 2)
                    part_caption = f"🎬 <b>{title}</b> (Part {idx}/{len(parts_list)})\n💾 Size: {part_size} MB"
                    send_telegram_message(token, chat_id, f"📤 Uploading Video Part {idx}/{len(parts_list)} to Telegram...")
                    send_telegram_video(token, chat_id, part_path, caption=part_caption)
                    cleanup_file(part_path)

                # Cleanup original file
                cleanup_file(orig_filepath)
        else:
            send_telegram_message(token, chat_id, f"⚠️ Video download failed: {res.get('message')}")
        return

    send_telegram_message(token, chat_id, "Unknown command or link. Type /help to see usage instructions.")

def start_bot_loop(token: str = DEFAULT_BOT_TOKEN):
    """Starts the long-polling Telegram Bot worker and background download server."""
    if not token:
        print("Telegram bot token required. Worker idle.")
        return

    # Start Flask direct download server on port 5050/PORT
    start_download_server(port=SERVER_PORT)

    url = f"https://api.telegram.org/bot{token.strip()}"
    last_update_id = 0
    print(f"🤖 Starting Universal Media Downloader Bot Worker (@MediaDownloader278Bot)...")

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
            elif resp.status_code == 409:
                print("Telegram API 409 Conflict. Retrying in 5s...")
                time.sleep(5)
        except Exception as e:
            print(f"Telegram long-polling error: {e}")
        time.sleep(2)

if __name__ == "__main__":
    start_bot_loop()

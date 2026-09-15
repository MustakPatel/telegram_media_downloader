import os
import glob
import subprocess
import concurrent.futures
import yt_dlp

DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))

def get_yt_dlp_options(extra_opts: dict = None, proxy: str = None) -> dict:
    """Returns base yt-dlp configuration dictionary with fast timeout, android/ios player clients, and geo-bypass."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 20,
        'retries': 3,
        'fragment_retries': 3,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DEFAULT_DOWNLOAD_DIR, '%(title).50s_%(id)s.%(ext)s'),
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb']
            }
        }
    }
    
    # Check for cookie file or env var
    cookie_path = os.environ.get('COOKIE_FILE') or os.path.join(os.path.dirname(__file__), 'cookies.txt')
    if os.path.exists(cookie_path):
        opts['cookiefile'] = cookie_path

    if proxy:
        opts['proxy'] = proxy
    if extra_opts:
        opts.update(extra_opts)
    return opts

def format_download_error(err_msg: str) -> str:
    """Formats raw yt-dlp error string into clear, human-readable Telegram alert."""
    msg_lower = err_msg.lower()
    
    if "redirected to the login page" in msg_lower or "exceeded the rate-limit" in msg_lower or "login required" in msg_lower:
        return """
⚠️ <b>INSTAGRAM / PLATFORM RATE-LIMIT</b> ⚠️

📌 <b>Reason:</b> Cloud Datacenter IP Rate-Limited
💡 <b>Explanation:</b> Instagram blocks anonymous media downloads from cloud server IPs.
👉 <b>Action:</b> Try downloading YouTube, TikTok, Twitter/X, Pinterest, or direct media links!
""".strip()
    elif "418" in msg_lower or "teapot" in msg_lower:
        return """
⚠️ <b>DOWNLOAD BLOCKED BY WEBSITE (HTTP 418)</b> ⚠️

📌 <b>Reason:</b> Cloudflare / Anti-Bot Shield
💡 <b>Explanation:</b> This website specifically blocks Cloud Data-Center IPs from downloading videos.
👉 <b>Action:</b> Try YouTube, Instagram Reels, TikTok, Twitter, or another public site.
""".strip()
    elif "403" in msg_lower or "forbidden" in msg_lower:
        return """
⚠️ <b>ACCESS FORBIDDEN (HTTP 403)</b> ⚠️

📌 <b>Reason:</b> Website Access Restricted
💡 <b>Explanation:</b> The target server denied access to the cloud downloader IP.
👉 <b>Action:</b> The video might be private, geoblocked, or DRM protected.
""".strip()
    elif "timed out" in msg_lower or "connection" in msg_lower:
        return """
⚠️ <b>CONNECTION TIMED OUT</b> ⚠️

📌 <b>Reason:</b> Server Connection Timed Out
💡 <b>Explanation:</b> The website server did not respond within the time limit.
""".strip()
    elif "confirm your age" in msg_lower or "private video" in msg_lower or "members-only" in msg_lower:
        return """
⚠️ <b>PRIVATE / AGE RESTRICTED CONTENT</b> ⚠️

📌 <b>Reason:</b> Account Login Required
💡 <b>Explanation:</b> This specific video is set to Private or requires a signed-in account on the target site.
""".strip()
    else:
        clean_err = err_msg.replace("ERROR:", "").strip()
        if len(clean_err) > 200:
            clean_err = clean_err[:200] + "..."
        return f"""
⚠️ <b>VIDEO DOWNLOAD UNABLE TO COMPLETE</b> ⚠️

📌 <b>Detail:</b> <code>{clean_err}</code>
💡 <b>Note:</b> Please check if the URL link is valid and public!
""".strip()

def extract_media_info(url: str, proxy: str = None) -> dict:
    """Extracts metadata from any web video/audio URL without downloading the file."""
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    opts = get_yt_dlp_options({'extract_flat': True}, proxy=proxy)
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {"status": "error", "message": format_download_error("Could not extract media metadata.")}
            
            title = info.get("title", "Web Media Video")
            duration = info.get("duration", 0)
            uploader = info.get("uploader", info.get("extractor_key", "Web Stream"))
            thumbnail = info.get("thumbnail", "")
            filesize = info.get("filesize", info.get("filesize_approx", 0))

            duration_str = f"{int(duration // 60)}m {int(duration % 60)}s" if duration else "Unknown"
            filesize_mb = round(filesize / (1024 * 1024), 2) if filesize else 0.0

            return {
                "status": "success",
                "title": title,
                "duration": duration_str,
                "uploader": uploader,
                "thumbnail": thumbnail,
                "filesize_mb": filesize_mb,
                "url": url
            }
    except Exception as e:
        return {"status": "error", "message": format_download_error(str(e))}

def split_video(input_filepath: str, max_part_size_mb: float = 40.0) -> list:
    """Splits video into parts under max_part_size_mb using fast FFmpeg stream copy."""
    if not os.path.exists(input_filepath):
        return [input_filepath]
        
    orig_size_mb = os.path.getsize(input_filepath) / (1024 * 1024)
    if orig_size_mb <= max_part_size_mb:
        return [input_filepath]

    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_filepath]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        duration = float(res.stdout.strip())
    except Exception:
        duration = 300.0

    num_parts = int(orig_size_mb // max_part_size_mb) + 1
    part_duration = duration / num_parts

    parts = []
    base, ext = os.path.splitext(input_filepath)

    for i in range(num_parts):
        start_time = i * part_duration
        part_path = f"{base}_part{i+1}{ext}"
        split_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", input_filepath,
            "-t", str(part_duration),
            "-c", "copy",
            part_path
        ]
        subprocess.run(split_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(part_path):
            parts.append(part_path)

    return parts if parts else [input_filepath]

def _download_video_internal(url: str, proxy: str = None) -> dict:
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    opts = get_yt_dlp_options(proxy=proxy)
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            base, _ = os.path.splitext(filename)
            mp4_filename = base + ".mp4"
            
            actual_filepath = mp4_filename if os.path.exists(mp4_filename) else filename
            if not os.path.exists(actual_filepath):
                matched = glob.glob(os.path.join(DEFAULT_DOWNLOAD_DIR, "*"))
                if matched:
                    actual_filepath = matched[-1]

            size_bytes = os.path.getsize(actual_filepath) if os.path.exists(actual_filepath) else 0
            size_mb = round(size_bytes / (1024 * 1024), 2)

            return {
                "status": "success",
                "filepath": actual_filepath,
                "filename": os.path.basename(actual_filepath),
                "filesize_mb": size_mb,
                "title": info.get("title", "Downloaded Video")
            }
    except Exception as e:
        return {"status": "error", "message": format_download_error(str(e))}

def download_video(url: str, timeout_sec: int = 120, proxy: str = None) -> dict:
    """Downloads video with a strict hard timeout of 120s to prevent infinite hanging on blocked links."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_download_video_internal, url, proxy)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            return {
                "status": "error",
                "message": format_download_error("Download timed out (120s Limit). Connection timed out.")
            }

def _download_audio_internal(url: str, proxy: str = None) -> dict:
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    opts = get_yt_dlp_options({
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DEFAULT_DOWNLOAD_DIR, '%(title).50s_%(id)s.%(ext)s'),
    }, proxy=proxy)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            mp3_filepath = base + ".mp3"

            actual_filepath = mp3_filepath if os.path.exists(mp3_filepath) else filename
            size_bytes = os.path.getsize(actual_filepath) if os.path.exists(actual_filepath) else 0
            size_mb = round(size_bytes / (1024 * 1024), 2)

            return {
                "status": "success",
                "filepath": actual_filepath,
                "filename": os.path.basename(actual_filepath),
                "filesize_mb": size_mb,
                "title": info.get("title", "Downloaded Audio")
            }
    except Exception as e:
        return {"status": "error", "message": format_download_error(str(e))}

def download_audio(url: str, timeout_sec: int = 120, proxy: str = None) -> dict:
    """Extracts MP3 audio with strict 120s hard timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_download_audio_internal, url, proxy)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            return {
                "status": "error",
                "message": "⏱️ Audio Extraction Timed Out (120s Limit). This site blocks cloud server connections."
            }

def cleanup_file(filepath: str):
    """Safely removes temporary download file after dispatching to Telegram."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Cleaned temp file: {filepath}")
    except Exception as e:
        print(f"Cleanup error for {filepath}: {e}")

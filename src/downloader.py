import os
import glob
import subprocess
import concurrent.futures
import yt_dlp

DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))

def get_yt_dlp_options(extra_opts: dict = None, proxy: str = None) -> dict:
    """Returns base yt-dlp configuration dictionary with fast timeout and geo-bypass."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 15,
        'retries': 2,
        'fragment_retries': 2,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'format': 'best/bestvideo+bestaudio',
        'outtmpl': os.path.join(DEFAULT_DOWNLOAD_DIR, '%(title).50s_%(id)s.%(ext)s'),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    if proxy:
        opts['proxy'] = proxy
    if extra_opts:
        opts.update(extra_opts)
    return opts

def extract_media_info(url: str, proxy: str = None) -> dict:
    """Extracts metadata from any web video/audio URL without downloading the file."""
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    opts = get_yt_dlp_options({'extract_flat': True}, proxy=proxy)
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {"status": "error", "message": "Could not extract media metadata."}
            
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
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "connection" in err_msg.lower():
            err_msg = "ISP/Domain Blocked (Connection Timed Out). Website requires VPN/Proxy on server."
        return {"status": "error", "message": err_msg}

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
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "connection" in err_msg.lower():
            err_msg = "ISP/Domain Blocked (Connection Timed Out). Website requires VPN/Proxy on server."
        return {"status": "error", "message": err_msg}

def download_video(url: str, timeout_sec: int = 120, proxy: str = None) -> dict:
    """Downloads video with a strict hard timeout of 120s to prevent infinite hanging on blocked links."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_download_video_internal, url, proxy)
        try:
            return future.result(timeout=timeout_sec)
        except concurrent.futures.TimeoutError:
            return {
                "status": "error",
                "message": "⏱️ Download Timed Out (120s Limit). This site blocks cloud server connections or has anti-bot Cloudflare protection."
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
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "connection" in err_msg.lower():
            err_msg = "ISP/Domain Blocked (Connection Timed Out). Website requires VPN/Proxy on server."
        return {"status": "error", "message": err_msg}

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

import os
import glob
import yt_dlp

DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))

def get_yt_dlp_options(extra_opts: dict = None) -> dict:
    """Returns base yt-dlp configuration dictionary."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DEFAULT_DOWNLOAD_DIR, '%(title).50s_%(id)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    if extra_opts:
        opts.update(extra_opts)
    return opts

def extract_media_info(url: str) -> dict:
    """
    Extracts metadata from any web video/audio URL without downloading the file.
    Supports YouTube, Instagram, Twitter, TikTok, HLS/m3u8, HTML5 video pages, etc.
    """
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    opts = get_yt_dlp_options({'extract_flat': True})
    
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
        return {"status": "error", "message": str(e)}

def download_video(url: str) -> dict:
    """
    Downloads media video in MP4 format.
    Returns file path, filesize_mb, and title.
    """
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    opts = get_yt_dlp_options()
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Ensure mp4 extension after format merge
            base, _ = os.path.splitext(filename)
            mp4_filename = base + ".mp4"
            
            actual_filepath = mp4_filename if os.path.exists(mp4_filename) else filename
            if not os.path.exists(actual_filepath):
                # Search for any matched file in download folder
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
        return {"status": "error", "message": str(e)}

def download_audio(url: str) -> dict:
    """
    Extracts audio from video URL and converts it into MP3 format.
    """
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
    opts = get_yt_dlp_options({
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DEFAULT_DOWNLOAD_DIR, '%(title).50s_%(id)s.%(ext)s'),
    })

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
        return {"status": "error", "message": str(e)}

def cleanup_file(filepath: str):
    """Safely removes temporary download file after dispatching to Telegram."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            print(f"Cleaned temp file: {filepath}")
    except Exception as e:
        print(f"Cleanup error for {filepath}: {e}")

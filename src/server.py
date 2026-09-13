from flask import Flask, send_from_directory, jsonify
import os
import sys
import threading

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_dir = os.path.abspath(os.path.dirname(__file__))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from src.downloader import DEFAULT_DOWNLOAD_DIR
except ModuleNotFoundError:
    from downloader import DEFAULT_DOWNLOAD_DIR

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({"status": "active", "service": "Universal Media Download Server"})

@app.route("/health")
def health():
    return "OK", 200

@app.route("/download/<path:filename>")
def download_file(filename):
    """Serves direct high-speed video/audio file download & streaming."""
    return send_from_directory(DEFAULT_DOWNLOAD_DIR, filename, as_attachment=True)

import time
import requests

def keep_alive_ping_worker():
    """Pings public URL every 8 minutes to prevent Render Free Tier spin-down."""
    public_url = os.environ.get("RENDER_EXTERNAL_URL", "https://telegram-media-downloader-myae.onrender.com")
    print(f"💓 Keep-Alive Worker initialized for {public_url}")
    while True:
        time.sleep(480) # 8 minutes
        try:
            r = requests.get(f"{public_url.rstrip('/')}/health", timeout=15)
            print(f"💓 Keep-Alive Ping Status: {r.status_code}")
        except Exception as e:
            print(f"Keep-Alive ping error: {e}")

def start_download_server(port: int = None):
    """Launches Flask download server in background daemon thread binding to $PORT for Render health check."""
    if port is None:
        port = int(os.environ.get("PORT", 10000))
    try:
        t = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False), daemon=True)
        t.start()
        print(f"🌐 Direct Download & Streaming Server live on 0.0.0.0:{port}!")

        # Launch Keep-Alive ping worker to prevent Render Free Tier sleep
        ka = threading.Thread(target=keep_alive_ping_worker, daemon=True)
        ka.start()
    except Exception as e:
        print(f"Error starting download server: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.downloader import extract_media_info, get_yt_dlp_options
except ModuleNotFoundError:
    from downloader import extract_media_info, get_yt_dlp_options

def test_yt_dlp_options():
    opts = get_yt_dlp_options()
    assert isinstance(opts, dict)
    assert opts["quiet"] is True
    assert "format" in opts

def test_extract_media_info_structure():
    # Test metadata extraction logic structure
    res = extract_media_info("https://www.youtube.com/watch?v=BaW_jenozKc")
    assert "status" in res
    if res["status"] == "success":
        assert "title" in res
        assert "duration" in res
        assert "filesize_mb" in res

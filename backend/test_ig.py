import sys
sys.path.insert(0, '.')
import yt_dlp
opts = {'cookiefile': 'cookies.txt', 'quiet': True}
with yt_dlp.YoutubeDL(opts) as ydl:
    try:
        info = ydl.extract_info('https://www.instagram.com/reel/DEeE1ZcI8H_', download=False)
        print(f"Likes: {info.get('like_count')}, Views: {info.get('view_count')}, Play count: {info.get('play_count')}, Comments: {info.get('comment_count')}")
    except Exception as e:
        print(f"Error: {e}")

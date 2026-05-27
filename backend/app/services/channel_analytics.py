import random
import logging
from typing import Dict, Any, List
import yt_dlp
import urllib.parse

logger = logging.getLogger(__name__)

def generate_mock_channel_analytics(channel_id: str) -> Dict[str, Any]:
    """
    Generates realistic mock analytics data for a channel to demonstrate
    trend detection, catalog effectiveness, and competitor benchmarking.
    Now dynamically fetches real channel data based on the channel_id.
    """
    
    top_hooks = []
    # Default mock values
    channel_name = f"{channel_id.capitalize()} Channel"
    profile_pic = None
    
    # Try to fetch actual channel data
    try:
        # Decode the channel_id if it's URL-encoded
        query = urllib.parse.unquote(channel_id)
        
        # Determine the search query
        if query.startswith("http") or query.startswith("@"):
            search_query = query
            if query.startswith("@"):
                search_query = f"https://www.youtube.com/{query}/videos"
        else:
            search_query = f"ytsearch1:{query}"
            
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
            'playlistend': 3
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            
            entries = []
            if info and 'entries' in info:
                # ytsearch1 returns a video entry, from which we can get the channel URL
                info_entries = list(info['entries']) # type: ignore
                if search_query.startswith("ytsearch1:"):
                    if len(info_entries) > 0 and info_entries[0]:
                        video_entry = info_entries[0]
                        channel_url = video_entry.get('channel_url')
                        if channel_url:
                            channel_name = video_entry.get('channel', video_entry.get('uploader', channel_name))
                            # Now fetch the videos from the channel
                            ydl_opts_channel = {
                                'extract_flat': True,
                                'playlistend': 3,
                                'quiet': True,
                                'no_warnings': True
                            }
                            with yt_dlp.YoutubeDL(ydl_opts_channel) as ydl_chan:
                                chan_info = ydl_chan.extract_info(f"{channel_url}/videos", download=False)
                                if chan_info and 'entries' in chan_info:
                                    entries = [e for e in chan_info['entries'] if e]
                                thumbnails = chan_info.get('thumbnails')
                                if thumbnails:
                                    profile_pic = thumbnails[-1].get('url')
                else:
                    # direct channel url
                    entries = [e for e in info['entries'] if e] # type: ignore
                    if 'channel' in info:
                        channel_name = info['channel']
                    elif 'uploader' in info:
                        channel_name = info['uploader']
                    elif len(entries) > 0 and 'uploader' in entries[0]:
                        channel_name = entries[0]['uploader']
                    
                    thumbnails = info.get('thumbnails')
                    if thumbnails:
                        profile_pic = thumbnails[-1].get('url')
            
            # Populate hooks with actual videos
            for idx, entry in enumerate(entries[:3]):
                title = entry.get('title', f"Video {idx+1}")
                vid_id = entry.get('id', f"v{idx+1}")
                # flat extraction for videos might not have view_count, so fallback to random
                views = entry.get('view_count') or random.randint(100000, 5000000)
                
                # Mock a hook based on the real title
                hook_text = f"In this video we are going to look at {title}. You won't believe what happens!"
                
                top_hooks.append({
                    "id": vid_id,
                    "title": title,
                    "hook_text": hook_text,
                    "retention": round(random.uniform(50.0, 80.0), 1),
                    "views": views,
                    "sentiment": random.choice(["Curiosity / Value", "High Stakes / Fear", "Spectacle / Anticipation", "Educational / Insight"])
                })
                
    except Exception as e:
        logger.warning(f"Failed to fetch channel data for {channel_id}: {e}")
        # Let it fallback if top_hooks is empty
        
    if not top_hooks:
        # Fallback to the original mock data
        top_hooks = [
            {
                "id": "v1",
                "title": "I Survived 50 Hours In Antarctica",
                "hook_text": "We are standing in the coldest place on earth, and if this heater breaks, we die.",
                "retention": 74.5,
                "views": 2500000,
                "sentiment": "High Stakes / Fear"
            },
            {
                "id": "v2",
                "title": "How To Build A $1M Business With Zero Dollars",
                "hook_text": "This exact framework made me my first million, and I'm giving it to you for free.",
                "retention": 65.2,
                "views": 850000,
                "sentiment": "Curiosity / Value"
            },
            {
                "id": "v3",
                "title": "I Tried The World's Hottest Pepper",
                "hook_text": "This tiny pepper ranks 2 million on the Scoville scale, and I'm about to eat the whole thing.",
                "retention": 61.8,
                "views": 1200000,
                "sentiment": "Spectacle / Anticipation"
            }
        ]
        
    # 1. Trend Detection (Hook Retention over last 12 weeks)
    trends = []
    base_retention = random.randint(35, 55) # Base % retention at 15s
    for i in range(12, 0, -1):
        # Simulate slight upward trend
        retention = base_retention + random.uniform(-5, 5) + (12 - i) * 1.5
        trends.append({
            "week": f"Week {-i}",
            "retention": round(retention, 1),
            "views": random.randint(50000, 500000)
        })
        
    # 2. Competitor Benchmarking
    benchmarks = [
        {"category": "This Channel", "retention": round(float(trends[-1]["retention"]), 1), "fill": "#8b5cf6"}, # Indigo
        {"category": "Industry Average", "retention": 35.5, "fill": "#3f3f46"}, # Zinc
        {"category": "Top 1% Creators", "retention": 68.2, "fill": "#10b981"}, # Emerald
    ]
    
    return {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "profile_pic": profile_pic,
        "trends": trends,
        "benchmarks": benchmarks,
        "top_hooks": top_hooks,
        "summary": f"{channel_name} shows a strong upward trend in hook retention, recently surpassing the industry average. The best performing hooks rely heavily on dynamic sentiments."
    }

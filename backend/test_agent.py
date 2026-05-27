import os
from dotenv import load_dotenv
from app.services.agent import initialize_session, send_chat_message

load_dotenv()

video_a = {
    "video_id": "test_a",
    "title": "Test A",
    "platform": "youtube",
    "metrics": {"views": 100},
    "engagement_rate": 5,
    "transcript": [{"text": "Hi guys", "start": 0, "duration": 5}]
}
video_b = {
    "video_id": "test_b",
    "title": "Test B",
    "platform": "youtube",
    "metrics": {"views": 200},
    "engagement_rate": 10,
    "transcript": [{"text": "Hello everyone", "start": 0, "duration": 5}]
}

print("Initializing...")
res1 = initialize_session("test_session_abc", video_a, video_b)
print("Initial hook length:", len(res1["hook_analysis"]))

print("\nSending chat 1...")
res2 = send_chat_message("test_session_abc", "Which one is better?")
print("Chat reply 1:", res2["reply"])

print("\nSending chat 2...")
res3 = send_chat_message("test_session_abc", "more info")
print("Chat reply 2:", res3["reply"])

import requests

# Test the endpoints of the CreatorJoy backend
def run_test():
    base_url = "http://127.0.0.1:8000"
    
    print("Testing /health...")
    health_res = requests.get(f"{base_url}/health")
    print(health_res.status_code, health_res.json())
    
    print("\nTesting /analyze...")
    session_id = "test_session_123"
    analyze_payload = {
        "url_a": "https://www.youtube.com/watch?v=jNQXAC9IVRw", # Me at the zoo
        "url_b": "https://www.youtube.com/watch?v=9bZkp7q19f0", # Gangnam style
        "session_id": session_id
    }
    analyze_res = requests.post(f"{base_url}/analyze", json=analyze_payload, stream=True)
    print(analyze_res.status_code)
    try:
        import json
        final_data = None
        for chunk in analyze_res.iter_lines():
            if chunk:
                line = chunk.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        continue
                    msg = json.loads(data_str)
                    if msg["type"] == "progress":
                        print("Progress:", msg["message"])
                    elif msg["type"] == "complete":
                        final_data = msg["data"]
                    elif msg["type"] == "error":
                        print("Error:", msg["message"])
                        
        if final_data:
            print("Hook analysis length:", len(final_data.get("hook_analysis", "")))
            print("Is mock:", final_data.get("is_mock_analysis"))
        
        print("\nTesting /chat/stream...")
        chat_payload = {
            "session_id": session_id,
            "message": "What is the hook of video A?"
        }
        chat_res = requests.post(f"{base_url}/chat/stream", json=chat_payload, stream=True)
        print("Chat status:", chat_res.status_code)
        for chunk in chat_res.iter_content(chunk_size=None):
            if chunk:
                print(chunk.decode("utf-8"), end="")
        print()
    except Exception as e:
        print("Error parsing analyze response:", e, analyze_res.text)

if __name__ == "__main__":
    run_test()

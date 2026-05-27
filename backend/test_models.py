import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
try:
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    models = client.models.list()
    print("Available models:")
    for m in models:
        print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")

import requests
import re
res = requests.get('https://www.instagram.com/reel/C8qLz-XyU9t/', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
print(re.search(r'<meta property="og:title" content="(.*?)"', res.text))
print(re.search(r'<meta property="og:description" content="(.*?)"', res.text))

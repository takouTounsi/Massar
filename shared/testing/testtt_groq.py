import os
import requests

r = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
        "Content-Type": "application/json"
    },
    json={
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "user",
                "content": "Say hello"
            }
        ]
    }
)

print(r.status_code)
print(r.text)
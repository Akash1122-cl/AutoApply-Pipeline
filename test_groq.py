import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
print(f"Key found: {api_key[:10]}...{api_key[-5:] if api_key else 'None'}")

client = Groq(api_key=api_key)
try:
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": "Explain the importance of fast language models"}],
        model="llama-3.3-70b-versatile",
    )
    print(chat_completion.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

SYSTEM = """You are Akash AI, Akash's personal AI assistant.
Be concise, practical, proactive, and honest.
Use clear English or Telugu-English naturally based on Akash's style.
Help with coding, research, planning, and everyday tasks.
Never claim an action was completed unless you actually performed it."""

def chat(message: str) -> str:
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": message},
            ],
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def main():
    print("Akash AI — online")
    print("Type 'exit' to quit.")

    while True:
        try:
            message = input("\nYou > ").strip()
            if message.lower() in {"exit", "quit"}:
                break
            if message:
                print(f"\nAkash AI > {chat(message)}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()

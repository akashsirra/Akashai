import os
import httpx
from dotenv import load_dotenv
from memory import init_db, save_message, get_recent_messages, clear_memory

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

SYSTEM = """You are Akash AI, Akash's personal AI assistant.
Be concise, practical, proactive, and honest.
Use clear English or Telugu-English naturally based on Akash's style.
Help with coding, research, planning, debugging, and everyday tasks.
Use conversation history to maintain context.
Never claim an action was completed unless you actually performed it."""

def chat(message: str) -> str:
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    history = get_recent_messages(20)
    messages = [{"role": "system", "content": SYSTEM}, *history,
                {"role": "user", "content": message}]

    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/akashsirra/Akashai",
            "X-Title": "Akash AI",
        },
        json={"model": MODEL, "messages": messages},
        timeout=120,
    )
    response.raise_for_status()
    answer = response.json()["choices"][0]["message"]["content"]
    save_message("user", message)
    save_message("assistant", answer)
    return answer

def main():
    init_db()
    print("Akash AI — online")
    print("Memory: enabled")
    print("Commands: /memory, /clear, exit")

    while True:
        try:
            message = input("\nYou > ").strip()
            if not message:
                continue
            if message.lower() in {"exit", "quit"}:
                break
            if message == "/memory":
                print(f"\nStored messages: {len(get_recent_messages(100000))}")
                continue
            if message == "/clear":
                clear_memory()
                print("\nMemory cleared.")
                continue
            print(f"\nAkash AI > {chat(message)}")
        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()

import json
import os
import re
import subprocess
from html import unescape
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

from memory import init_db, save_message, get_recent_messages, clear_memory

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM = """You are Akash AI, Akash's personal AI assistant.
Be concise, practical, proactive, and honest.
Use clear English or Telugu-English naturally based on Akash's style.
You can search the public web and use safe local tools.
For tasks requiring tools, actually use them instead of pretending.
Never claim an action was completed unless it actually happened.
When web results are used, mention relevant source URLs briefly."""

def search_web(query: str, max_results: int = 5) -> str:
    url = "https://html.duckduckgo.com/html/?q=" + quote(query)
    r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 AkashAI/0.1"},
                  timeout=20, follow_redirects=True)
    r.raise_for_status()
    blocks = re.findall(r'<div class="result__body".*?</div>\s*</div>', r.text, re.S)
    results = []
    for block in blocks[:max_results]:
        m = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        link = unescape(m.group(1))
        title = unescape(re.sub(r"<.*?>", "", m.group(2))).strip()
        sm = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', block, re.S)
        snippet = unescape(re.sub(r"<.*?>", "", sm.group(1))).strip() if sm else ""
        results.append(f"{len(results)+1}. {title}\n   {link}\n   {snippet}")
    return "\n\n".join(results) if results else "No web results found."

def run_shell(command: str) -> str:
    blocked = [
        r"\brm\s+-rf\b", r"\bmkfs\b", r"\bdd\s+if=", r":\(\)\s*\{",
        r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b",
        r"\bgit\s+push\s+--force\b", r"\bgit\s+reset\s+--hard\b",
    ]
    if any(re.search(p, command, re.I) for p in blocked):
        return "BLOCKED: potentially destructive command."
    try:
        p = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=20)
        output = (p.stdout + p.stderr).strip()
        return output[-12000:] if output else f"Command exited with code {p.returncode}."
    except subprocess.TimeoutExpired:
        return "Command timed out after 20 seconds."
    except Exception as e:
        return f"Command failed: {e}"

TOOLS = [
    {"type":"function","function":{
        "name":"search_web",
        "description":"Search the public web for current or factual information.",
        "parameters":{"type":"object","properties":{
            "query":{"type":"string","description":"Search query"},
            "max_results":{"type":"integer","minimum":1,"maximum":5}
        },"required":["query"]}
    }},
    {"type":"function","function":{
        "name":"run_shell",
        "description":"Run a local non-destructive shell command for diagnostics, development, and file inspection.",
        "parameters":{"type":"object","properties":{
            "command":{"type":"string","description":"Shell command to run"}
        },"required":["command"]}
    }},
]

def execute_tool(name, arguments):
    if name == "search_web":
        return search_web(arguments["query"], arguments.get("max_results", 5))
    if name == "run_shell":
        return run_shell(arguments["command"])
    return f"Unknown tool: {name}"

def request_model(messages):
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    r = httpx.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/akashsirra/Akashai",
            "X-Title": "Akash AI",
        },
        json={"model": MODEL, "messages": messages, "tools": TOOLS, "tool_choice": "auto"},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]

def chat(message: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, *get_recent_messages(20),
                {"role": "user", "content": message}]
    for _ in range(5):
        assistant = request_model(messages)
        calls = assistant.get("tool_calls") or []
        if not calls:
            answer = assistant.get("content") or ""
            save_message("user", message)
            save_message("assistant", answer)
            return answer
        messages.append(assistant)
        for call in calls:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
                result = execute_tool(call["function"]["name"], args)
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append({"role":"tool", "tool_call_id":call["id"], "content":result})
    return "I reached the tool-step limit before completing the task."

def main():
    init_db()
    print("Akash AI — online")
    print("Memory: enabled | Tools: web + shell")
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

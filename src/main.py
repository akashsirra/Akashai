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
After receiving useful tool results, synthesize the answer instead of repeatedly calling the same tool.
For web questions, normally one good search is enough; only search again if the first result is empty or clearly insufficient.
Never claim an action was completed unless it actually happened.
When web results are used, mention relevant source URLs briefly."""

def search_web(query: str, max_results: int = 5) -> str:
    """Return compact search results from public HTML search endpoints."""
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 16) AkashAI/0.1"}
    engines = [
        ("https://html.duckduckgo.com/html/?q=", "ddg"),
        ("https://www.google.com/search?q=", "google"),
    ]
    last_error = None

    for base, engine in engines:
        try:
            r = httpx.get(
                base + quote(query),
                headers=headers,
                timeout=20,
                follow_redirects=True,
            )
            r.raise_for_status()
            html = r.text
            results = []

            if engine == "ddg":
                matches = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    html,
                    re.S | re.I,
                )
                snippets = re.findall(
                    r'<(?:a|div)[^>]+class="result__snippet"[^>]*>(.*?)</(?:a|div)>',
                    html,
                    re.S | re.I,
                )
                for i, (link, title_html) in enumerate(matches[:max_results]):
                    title = unescape(re.sub(r"<.*?>", "", title_html)).strip()
                    link = unescape(link)
                    snippet = ""
                    if i < len(snippets):
                        snippet = unescape(re.sub(r"<.*?>", "", snippets[i])).strip()
                    if title and link:
                        results.append(f"{len(results)+1}. {title}\n   {link}\n   {snippet}")

            else:
                # Google result pages commonly expose result links as /url?q=...
                matches = re.findall(
                    r'<a[^>]+href="(/url\\?q=[^"]+)"[^>]*>(.*?)</a>',
                    html,
                    re.S | re.I,
                )
                seen = set()
                for link, title_html in matches:
                    link = unescape(link)
                    m = re.search(r"/url\\?q=([^&]+)", link)
                    real = unescape(m.group(1)) if m else link
                    title = unescape(re.sub(r"<.*?>", "", title_html)).strip()
                    if real.startswith("http") and title and real not in seen:
                        seen.add(real)
                        results.append(f"{len(results)+1}. {title}\n   {real}")
                        if len(results) >= max_results:
                            break

            if results:
                return "\n\n".join(results)

        except Exception as e:
            last_error = e

    return f"No web results found. Search error: {last_error}" if last_error else "No web results found."

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

def request_model(messages, use_tools=True):
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
        json={**{"model": MODEL, "messages": messages}, **({"tools": TOOLS, "tool_choice": "auto"} if use_tools else {})},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]

def chat(message: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, *get_recent_messages(20),
                {"role": "user", "content": message}]

    # Reliable fast path for web/current-information requests.
    # Some free OpenRouter models are inconsistent with native tool calling,
    # so do the search deterministically and ask the model only to synthesize.
    web_intent = re.search(
        r"\b(latest|today|current|recent|news|search the web|look up|what happened|who is)\b",
        message,
        re.I,
    )
    if web_intent:
        try:
            web_results = search_web(message, 5)
            messages.append({
                "role": "system",
                "content": "Web search results are below. Use them to answer the user's request. "
                           "Cite the source URLs shown in the results. Do not call another tool unless "
                           "the results are clearly empty.\n\n" + web_results,
            })
            assistant = request_model(messages, use_tools=False)
            answer = assistant.get("content") or ""
            if answer:
                save_message("user", message)
                save_message("assistant", answer)
                return answer
        except Exception as e:
            messages.append({
                "role": "system",
                "content": f"Web search failed: {e}. Answer honestly without pretending you searched."
            })

    used_calls = set()
    for _ in range(8):
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
                name = call["function"]["name"]
                raw_args = call["function"].get("arguments") or "{}"
                args = json.loads(raw_args)
                call_key = (name, json.dumps(args, sort_keys=True))
                if call_key in used_calls:
                    result = "This exact tool call was already executed. Use the existing result and answer the user."
                else:
                    used_calls.add(call_key)
                    result = execute_tool(name, args)
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append({"role":"tool", "tool_call_id":call["id"], "content":result})
    return "I could not complete the tool-assisted task within the agent limit. The available tool results were gathered, but the model did not produce a final answer."

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

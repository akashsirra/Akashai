import json
import os
import re
import subprocess
import threading
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
try:
    from .gptoss import configured as gptoss_configured, chat as gptoss_chat
except ImportError:
    from gptoss import configured as gptoss_configured, chat as gptoss_chat

try:
    from .memory import init_db, save_message, get_recent_messages, get_facts, clear_memory
except ImportError:
    from memory import init_db, save_message, get_recent_messages, get_facts, clear_memory

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
API_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = 90

SYSTEM = """You are Akash AI, Akash's personal AI assistant.
Be concise, practical, proactive, and honest.
Use natural English or Telugu-English based on the user's style.
You have access to web search and a safe local shell.
Never claim you performed an action unless it actually happened.
When web research is supplied, answer from those results and cite the source URLs.
Do not invent facts, sources, links, or search results.
For current/latest/news questions, prefer recent dated sources and clearly say when information is unavailable."""

def clean_html(text):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()

def fetch_url(url, limit=12000):
    r = httpx.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 AkashAI/1.0"},
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    return clean_html(r.text)[:limit], str(r.url)

def news_search(query, max_results=6):
    """Reliable current-news search using Google News RSS, no search API key required."""
    url = (
        "https://news.google.com/rss/search?q="
        + quote(query)
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )
    r = httpx.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 AkashAI/1.0"},
        timeout=20,
        follow_redirects=True,
    )
    r.raise_for_status()
    root = ET.fromstring(r.text)
    items = []
    for item in root.findall(".//item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        source = item.find("source")
        source_name = (source.text or "").strip() if source is not None else ""
        desc = clean_html(item.findtext("description") or "")
        if title and link:
            items.append(
                f"{len(items)+1}. {title}\n"
                f"   Source: {source_name}\n"
                f"   Published: {pub}\n"
                f"   URL: {link}\n"
                f"   Summary: {desc[:500]}"
            )
    return "\n\n".join(items) if items else "No current news results found."

def web_search(query, max_results=6):
    """General web search with DDG HTML plus a news fallback."""
    headers = {"User-Agent": "Mozilla/5.0 AkashAI/1.0"}
    endpoints = [
        "https://html.duckduckgo.com/html/?q=",
        "https://lite.duckduckgo.com/lite/?q=",
    ]
    for base in endpoints:
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
            # Works with several DDG markup variants.
            pattern = re.compile(
                r"""<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""",
                re.S | re.I,
            )
            for link, title_html in pattern.findall(html):
                title = clean_html(title_html)
                link = unescape(link)
                if not link.startswith("http"):
                    continue
                if not title or len(title) < 3:
                    continue
                if "duckduckgo.com" in link:
                    continue
                if any(x[1] == link for x in results):
                    continue
                results.append((title, link))
                if len(results) >= max_results:
                    return "\n\n".join(
                        f"{i}. {title}\n   URL: {link}"
                        for i, (title, link) in enumerate(results, 1)
                    )
        except Exception:
            continue
    return news_search(query, max_results)

def search_web(query, max_results=6):
    news_words = r"\b(latest|today|current|recent|news|headline|headlines|what happened)\\b"
    if re.search(news_words, query, re.I):
        try:
            return news_search(query, max_results)
        except Exception as news_error:
            try:
                return web_search(query, max_results)
            except Exception as web_error:
                return f"WEB_SEARCH_ERROR: news={news_error}; web={web_error}"
    try:
        return web_search(query, max_results)
    except Exception as e:
        return f"WEB_SEARCH_ERROR: {e}"

def write_project_file(path, content):
    """Write a text file inside the current Akash AI project workspace."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    target = (root / path).resolve()
    if root not in target.parents and target != root:
        return "BLOCKED: path escapes the project."
    if any(part in {".git", ".venv", "__pycache__"} for part in target.parts):
        return "BLOCKED: protected path."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"WROTE {target.relative_to(root)} ({len(content)} bytes)"

def read_project_file(path):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    target = (root / path).resolve()
    if root not in target.parents and target != root:
        return "BLOCKED: path escapes the project."
    if not target.is_file():
        return f"NOT_FOUND: {path}"
    return target.read_text(encoding="utf-8")[:30000]

def run_shell(command):
    blocked = [
        r"\brm\\s+-rf\\b", r"\bmkfs\\b", r"\bdd\\s+if=",
        r":\\(\\)\\s*\\{", r"\bshutdown\\b", r"\breboot\\b",
        r"\bpoweroff\\b", r"\bgit\\s+push\\s+--force\\b",
        r"\bgit\\s+reset\\s+--hard\\b",
    ]
    if any(re.search(p, command, re.I) for p in blocked):
        return "BLOCKED: potentially destructive command."
    try:
        p = subprocess.run(
            command, shell=True, text=True, capture_output=True, timeout=20
        )
        output = (p.stdout + p.stderr).strip()
        return output[-12000:] if output else f"Command exited with code {p.returncode}."
    except subprocess.TimeoutExpired:
        return "Command timed out after 20 seconds."
    except Exception as e:
        return f"Command failed: {e}"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_project_file",
            "description": "Create or replace a source/config text file inside the project. Use this to build software.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_project_file",
            "description": "Read a project text file before modifying it.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        },
    },

    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the public web or current news.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a local non-destructive shell command for development and inspection.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]

def request_model(messages, use_tools=False):
    # A personal OpenAI-compatible GPT-OSS endpoint can be used without a
    # vendor API key. The current gptoss-proxy exposes chat completions but
    # does not implement OpenAI tool_calls, so tool-driven company work keeps
    # using the providers below.
    if gptoss_configured() and not use_tools:
        try:
            return gptoss_chat(messages)
        except Exception:
            # Fall through to configured vendor providers.
            pass

    if not API_KEY and not GROQ_API_KEY:
        if gptoss_configured():
            raise RuntimeError(
                "GPT-OSS endpoint failed. Check AI_COMPAT_URL or its upstream service."
            )
        raise RuntimeError("No AI provider configured. Set AI_COMPAT_URL, OPENROUTER_API_KEY, or GROQ_API_KEY.")

    payload = {"model": MODEL, "messages": messages}
    if use_tools:
        payload["tools"] = TOOLS
        payload["tool_choice"] = "auto"

    providers = []
    if API_KEY:
        providers.append((
            "OpenRouter",
            API_URL,
            API_KEY,
            {
                "HTTP-Referer": "https://github.com/akashsirra/Akashai",
                "X-Title": "Akash AI",
            },
            MODEL,
        ))
    if GROQ_API_KEY:
        providers.append((
            "Groq",
            GROQ_API_URL,
            GROQ_API_KEY,
            {},
            GROQ_MODEL,
        ))

    last_error = None
    for provider_name, url, api_key, extra_headers, model in providers:
        provider_payload = dict(payload)
        provider_payload["model"] = model
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **extra_headers,
        }
        try:
            r = httpx.post(url, headers=headers, json=provider_payload, timeout=TIMEOUT)
            if r.status_code == 429:
                last_error = f"{provider_name} returned 429 Too Many Requests"
                continue
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]
        except httpx.HTTPStatusError as e:
            last_error = f"{provider_name}: {e}"
            if e.response.status_code in {429, 502, 503, 504}:
                continue
            raise

    raise RuntimeError(
        (last_error or "All configured AI providers failed.")
        + ". Configure another provider or wait for the rate limit to reset."
    )



# --- Autonomous agent ------------------------------------------------------
AGENT_SYSTEM = """You are Akash AI Builder. BUILD working software, not ideas.
Inspect the repository, create/edit actual files, run tests/builds, inspect failures, fix them, and repeat.
For a monetizable product, choose a small paid workflow with a clear buyer and implement a usable MVP.
Never claim deployment, customers, payments, or revenue without evidence.
Prefer a complete small product over a large unfinished architecture."""

def execute_agent_task(task):
    messages = [{"role": "system", "content": AGENT_SYSTEM}, {"role": "user", "content": task}]
    max_steps = 16 if "build" in task.lower() else 8
    for _ in range(max_steps):
        assistant = request_model(messages, use_tools=True)
        calls = assistant.get("tool_calls") or []
        if not calls:
            return assistant.get("content") or "Task completed with no final response."
        messages.append(assistant)
        for call in calls:
            try:
                name = call["function"]["name"]
                args = json.loads(call["function"].get("arguments") or "{}")
                if name == "search_web":
                    result = search_web(args["query"], args.get("max_results", 6))
                elif name == "write_project_file":
                    result = write_project_file(args["path"], args["content"])
                elif name == "read_project_file":
                    result = read_project_file(args["path"])
                elif name == "run_shell":
                    result = run_shell(args["command"])
                else:
                    result = "Unknown tool."
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return "Agent reached its safety step limit. Partial work remains in the project; run the same build command again to continue from the current state."

def background_task(task):
    def worker():
        try:
            print("\\n\\n[Akash AI background task]\\n" + execute_agent_task(task) + "\\n")
        except Exception as e:
            print("\\n\\n[Akash AI background task error] " + str(e) + "\\n")
    threading.Thread(target=worker, daemon=True).start()

def looks_like_web_request(message):
    return bool(re.search(
        r"\b(latest|today|current|recent|news|search the web|look up|what happened|who is|price|weather)\\b",
        message,
        re.I,
    ))

def answer_with_web(message):
    results = search_web(message, 6)
    if results.startswith("WEB_SEARCH_ERROR:") or results == "No current news results found.":
        return None, results

    prompt = (
        "The user asked a current-information question. Below are live search results. "
        "Answer the user's exact request using ONLY the supplied results. "
        "For news, give concise bullet points and include the source name and URL for each point. "
        "Do not say you cannot search when results are present. Do not invent missing details.\n\n"
        f"SEARCH RESULTS:\n{results}"
    )
    facts = get_facts(30)
    fact_context = ("Known facts about Akash:\n- " + "\n- ".join(facts)) if facts else ""
    messages = [
        {"role": "system", "content": SYSTEM + ("\n\n" + fact_context if fact_context else "")},
        *get_recent_messages(10),
        {"role": "user", "content": message},
        {"role": "system", "content": prompt},
    ]
    answer = request_model(messages, use_tools=False).get("content") or ""
    return (answer or results), results

def chat(message):
    if looks_like_web_request(message):
        try:
            answer, raw = answer_with_web(message)
            if answer:
                save_message("user", message)
                save_message("assistant", answer)
                return answer
        except Exception as e:
            return f"I couldn't complete the live web lookup: {e}"

    messages = [
        {"role": "system", "content": SYSTEM},
        *get_recent_messages(20),
        {"role": "user", "content": message},
    ]
    used_calls = set()
    for _ in range(6):
        assistant = request_model(messages, use_tools=True)
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
                args = json.loads(call["function"].get("arguments") or "{}")
                key = (name, json.dumps(args, sort_keys=True))
                if key in used_calls:
                    result = "Already executed. Use the previous result and answer."
                else:
                    used_calls.add(key)
                    if name == "search_web":
                        result = search_web(args["query"], args.get("max_results", 6))
                    elif name == "write_project_file":
                        result = write_project_file(args["path"], args["content"])
                    elif name == "read_project_file":
                        result = read_project_file(args["path"])
                    else:
                        result = run_shell(args["command"])
            except Exception as e:
                result = f"Tool error: {e}"
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": result}
            )

    return "I couldn't finish the tool task within the execution limit."

def main():
    init_db()
    print("Akash AI — online")
    print(f"Model: {MODEL}")
    print("Memory: enabled | Web: live news + search | Shell: safe mode")
    print("Commands: /help, /build, /build <product>, /agent <task>, /money, /memory, /remember <fact>, /clear, /web <query>, /background <task>, /webui, exit")

    while True:
        try:
            message = input("\nYou > ").strip()
            if not message:
                continue
            if message.lower() in {"exit", "quit"}:
                break
            if message == "/money":
                from money import run as run_money_factory
                print("\nAkash AI > Money Factory started. Researching a real problem and preparing a launch package...")
                print(run_money_factory())
                continue
            if message.startswith("/money "):
                from money import run as run_money_factory
                topic = message[7:].strip()
                print("\nAkash AI > Money Factory started for: " + topic)
                print(run_money_factory(topic))
                continue
            if message == "/build":
                print("\nAkash AI > Builder agent started. It will inspect, build, test, and repair the product.")
                print(execute_agent_task(
                    "Build a complete small monetizable web MVP inside this repository. "
                    "Do not return an idea or business plan. Inspect the repo first, choose one simple B2B paid workflow, "
                    "implement the actual source code, landing page, core workflow, local persistence, pricing page, README, and tests. "
                    "Use dependencies practical on Android/Termux. Run tests and repair failures before finishing."
                ))
                continue
            if message.startswith("/build "):
                print("\nAkash AI > Builder agent started.")
                print(execute_agent_task(message[7:].strip() +
                    "\nIMPORTANT: build the actual software in this repository. Do not just research or write a plan. "
                    "Create files, run tests, fix failures, and leave a runnable MVP."))
                continue
            if message == "/help":
                print("\nAsk normally. Examples:")
                print("  What is the latest OpenAI news?")
                print("  Search the web for entry-level software jobs in Hyderabad.")
                print("  Show me the files in this project.")
                print("Commands: /memory /clear /web <query> exit")
                continue
            if message == "/memory":
                print(f"\nStored messages: {len(get_recent_messages(100000))}")
                facts = get_facts(100)
                print("Known facts:")
                for fact in facts:
                    print(" - " + fact)
                continue
            if message.startswith("/remember "):
                from memory import remember_fact
                fact = message[10:].strip()
                remember_fact(fact)
                print("\nAkash AI > Remembered.")
                continue
            if message == "/webui":
                from web import serve
                serve()
                continue
            if message == "/clear":
                clear_memory()
                print("\nMemory cleared.")
                continue
            if message.startswith("/web "):
                query = message[5:].strip()
                print(f"\nAkash AI > {search_web(query)}")
                continue
            if message.startswith("/agent "):
                print("\nAkash AI > " + execute_agent_task(message[7:].strip()))
                continue
            if message.startswith("/background "):
                background_task(message[12:].strip())
                print("\nAkash AI > Background task started.")
                continue
            print(f"\nAkash AI > {chat(message)}")
        except KeyboardInterrupt:
            print("\nBye.")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()

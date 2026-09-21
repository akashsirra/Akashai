# Akash AI

A personal Grok-style AI assistant built for Android/Termux.

## Features
- OpenRouter chat with configurable models
- Persistent conversation memory
- Long-term facts (/remember)
- Live news research via Google News RSS
- General web search
- Autonomous multi-step agent
- Background tasks
- Safe local shell tools
- Mobile-friendly local web UI
- SQLite local storage
- No framework-heavy server required

## Setup

    git clone https://github.com/akashsirra/Akashai.git
    cd Akashai
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env

Set OPENROUTER_API_KEY in .env.

## Run

    source .venv/bin/activate
    python src/main.py

Inside the CLI, run /webui and open http://127.0.0.1:8787.

## Commands
- /money — research and package one monetizable software opportunity
- /money <problem> — research a specific problem and prepare a launch package
- /web <query> — direct web search
- /agent <task> — autonomous multi-step task
- /background <task> — run a task in the background
- /remember <fact> — save a long-term fact
- /memory — inspect stored memory
- /clear — clear conversation and facts
- /webui — launch the mobile web interface
- /help — show commands

## Architecture
Akash AI -> OpenRouter -> memory -> live web/news -> Money Factory -> tool agent -> safe shell -> background worker -> Android web UI

The product is local-first: conversation memory stays in memory.db on the device unless you explicitly add external integrations.
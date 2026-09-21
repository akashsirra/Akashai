import re
from datetime import datetime
from pathlib import Path

from main import request_model, search_web

ROOT = Path(__file__).resolve().parents[1]
MONEY_DIR = ROOT / "money"
MONEY_DIR.mkdir(exist_ok=True)


def model(prompt):
    response = request_model([
        {
            "role": "system",
            "content": (
                "You are Akash AI Money Factory. Find practical software businesses "
                "a solo developer can launch. Prefer painful, recurring problems with "
                "clear buyers, low infrastructure cost, and an MVP that can ship fast. "
                "Never promise revenue or invent customers. Separate evidence from ideas."
            ),
        },
        {"role": "user", "content": prompt},
    ])
    return response.get("content") or ""


def market_research(topic=None):
    queries = [
        topic or "software problems small businesses freelancers agencies pay to solve 2026",
        "micro SaaS recurring revenue small business software opportunities 2026",
        "B2B software pain points India small businesses 2026",
    ]
    blocks = []
    for query in queries:
        try:
            blocks.append(f"QUERY: {query}\n{search_web(query, 5)}")
        except Exception as exc:
            blocks.append(f"QUERY: {query}\nERROR: {exc}")
    return "\n\n".join(blocks)


def create_plan(topic=None):
    research = market_research(topic)
    prompt = f"""Use the live research below to select ONE realistic micro-SaaS business.

RESEARCH:
{research}

Return:
# Product
# Paying customer
# Problem
# Why they may pay
# MVP (max 5 features)
# Pricing in INR
# Acquisition plan
# 7-day build plan
# Evidence
# Risks

Use source URLs from the research where available. Do not claim validation that the
research does not establish. The goal is a testable business, not guaranteed income.
"""
    plan = model(prompt)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (MONEY_DIR / f"plan-{stamp}.md").write_text("# Akash AI Money Factory\n\n" + plan + "\n", encoding="utf-8")
    (MONEY_DIR / "latest-plan.md").write_text("# Akash AI Money Factory\n\n" + plan + "\n", encoding="utf-8")
    return plan


def build_assets(plan):
    prompt = f"""Create launch assets for this proposed product.

PLAN:
{plan}

Produce:
1. Product name and one-line value proposition
2. Landing page headline, subheadline, 3 benefits, CTA
3. Pricing page copy with 2 paid tiers
4. 5 cold outreach messages for likely buyers
5. FAQ with 6 questions
6. MVP technical specification: pages, data model, API endpoints
7. First 10 customer acquisition actions

Keep everything concrete and small enough for a solo developer. Do not fabricate
testimonials, users, revenue, partnerships, or guarantees.
"""
    assets = model(prompt)
    (MONEY_DIR / "launch-assets.md").write_text("# Launch Assets\n\n" + assets + "\n", encoding="utf-8")
    return assets


def run(topic=None):
    plan = create_plan(topic)
    assets = build_assets(plan)
    return (
        "MONEY FACTORY BUILT THE NEXT BUSINESS PACKAGE.\n\n"
        "Created:\n"
        "  money/latest-plan.md\n"
        "  money/launch-assets.md\n"
        "  money/plan-<timestamp>.md\n\n"
        "The package contains one researched product idea, MVP scope, pricing, "
        "landing-page copy, outreach, and a first-customer plan.\n\n"
        + assets
    )

import sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"company.db"; SKILLS=ROOT/"skills"; COMPANIES=ROOT/"companies"
SKILLS.mkdir(exist_ok=True); COMPANIES.mkdir(exist_ok=True)

def now(): return datetime.now(timezone.utc).isoformat()
def conn():
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row; return c

def init_company_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS company(id TEXT PRIMARY KEY,name TEXT NOT NULL,mission TEXT DEFAULT '',status TEXT DEFAULT 'active',created_at TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,company_id TEXT,title TEXT,prompt TEXT,status TEXT DEFAULT 'queued',priority INTEGER DEFAULT 5,run_at TEXT,result TEXT DEFAULT '',created_at TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,company_id TEXT,action TEXT,details TEXT,status TEXT DEFAULT 'pending',created_at TEXT,decided_at TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,company_id TEXT,kind TEXT,message TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS employees(id TEXT PRIMARY KEY,company_id TEXT,name TEXT,role TEXT,system_prompt TEXT,status TEXT DEFAULT 'active');
        CREATE TABLE IF NOT EXISTS skills(name TEXT PRIMARY KEY,description TEXT,path TEXT,enabled INTEGER DEFAULT 1);
        """)
        if not c.execute("SELECT 1 FROM company LIMIT 1").fetchone():
            cid=str(uuid.uuid4()); t=now()
            c.execute("INSERT INTO company VALUES(?,?,?,?,?,?)",(cid,"Akash AI Company","Build and operate small software businesses.","active",t,t))
            for name,role,prompt in [
                ("CEO","CEO","Coordinate the company and request approvals for consequential actions."),
                ("Research Agent","Research","Research markets, competitors and customers using public sources."),
                ("Product Agent","Engineering","Build, test and repair software in the company workspace."),
                ("Sales Agent","Sales","Research prospects and draft outreach; never send automatically."),
                ("Marketing Agent","Marketing","Create factual marketing assets without fabricated claims."),
                ("Operations Agent","Operations","Track tasks, blockers, metrics and recurring work.")]:
                c.execute("INSERT INTO employees VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),cid,name,role,prompt,"active"))
        defaults=[
            ("market_research","Research a market and produce evidence-backed opportunity notes."),
            ("build_mvp","Build, test and repair a small MVP."),
            ("prospect_research","Find and qualify prospects and draft outreach without sending."),
            ("daily_ops","Review company state, blockers and next actions."),
            ("weekly_report","Produce a factual company operating report.")
        ]
        for n,d in defaults:
            p=str(SKILLS/(n+".md"))
            if not Path(p).exists(): Path(p).write_text("# "+n+"\n\n"+d+"\n",encoding="utf-8")
            c.execute("INSERT OR IGNORE INTO skills VALUES(?,?,?,1)",(n,d,p))

def company():
    init_company_db()
    with conn() as c: return dict(c.execute("SELECT * FROM company LIMIT 1").fetchone())

def log(kind,message):
    with conn() as c:c.execute("INSERT INTO events(company_id,kind,message,created_at) VALUES(?,?,?,?)",(company()["id"],kind,message,now()))

def queue_task(title,prompt,run_at=None,priority=5):
    init_company_db(); tid=str(uuid.uuid4()); t=now()
    with conn() as c:c.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)",(tid,company()["id"],title,prompt,"queued",priority,run_at or t,"",t,t))
    log("task_queued",title); return tid

def list_tasks(limit=20):
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM tasks ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,priority,created_at DESC LIMIT ?",(limit,)).fetchall()]

def claim_due_task():
    with conn() as c:
        x=c.execute("SELECT * FROM tasks WHERE status='queued' AND (run_at IS NULL OR run_at<=?) ORDER BY priority,created_at LIMIT 1",(now(),)).fetchone()
        if not x:return None
        c.execute("UPDATE tasks SET status='running',updated_at=? WHERE id=? AND status='queued'",(now(),x["id"]))
        return dict(x)

def finish_task(tid,result,status="done"):
    with conn() as c:c.execute("UPDATE tasks SET status=?,result=?,updated_at=? WHERE id=?",(status,result[-50000:],now(),tid))

def request_approval(action,details):
    aid=str(uuid.uuid4())
    with conn() as c:c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?)",(aid,company()["id"],action,details,"pending",now(),""))
    log("approval_required",action+": "+details); return aid

def approvals(limit=20):
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM approvals WHERE status='pending' ORDER BY created_at LIMIT ?",(limit,)).fetchall()]

def decide_approval(aid,status):
    if status not in ("approved","denied"): raise ValueError("invalid decision")
    with conn() as c:c.execute("UPDATE approvals SET status=?,decided_at=? WHERE id=? AND status='pending'",(status,now(),aid))

def events(limit=30):
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]

def employees():
    with conn() as c:return [dict(x) for x in c.execute("SELECT * FROM employees WHERE status='active'").fetchall()]

def schedule_daily():
    with conn() as c:x=c.execute("SELECT 1 FROM tasks WHERE title='Daily company operations' AND status IN ('queued','running')").fetchone()
    if not x: queue_task("Daily company operations","Run daily operations: inspect company state, perform low-risk research/build/analysis, and report blockers. Never send messages or spend money automatically.")

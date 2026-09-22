import os,time,logging
import httpx
from dotenv import load_dotenv
load_dotenv()
from main import chat,execute_agent_task,search_web
from company import init_company_db,company,queue_task,list_tasks,approvals,decide_approval,employees,schedule_daily

TOKEN=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
OWNER=os.getenv("TELEGRAM_OWNER_ID","").strip()
API="https://api.telegram.org/bot"+TOKEN

def api(method,payload=None):
    r=httpx.post(API+"/"+method,json=payload or {},timeout=60); r.raise_for_status()
    d=r.json()
    if not d.get("ok"): raise RuntimeError(d)
    return d.get("result")

def send(cid,text):
    text=str(text)
    for i in range(0,len(text),3900): api("sendMessage",{"chat_id":cid,"text":text[i:i+3900]})

def allowed(m): return str(m.get("from",{}).get("id",""))==OWNER

def report():
    c=company(); ts=list_tasks(10); ap=approvals(10)
    out=[f"🏢 {c['name']}","Status: "+c["status"],f"Active/queued tasks: {sum(x['status'] in ('queued','running') for x in ts)}"]
    if ap:
        out.append("⚠️ Pending approvals:")
        out += [f"• {a['id'][:8]} — {a['action']}: {a['details'][:180]}" for a in ap]
    out.append("📋 Recent work:")
    out += [f"• [{x['status']}] {x['title']}" for x in ts[:8]]
    return "\n".join(out)

def handle(m):
    if not allowed(m): return
    cid=m["chat"]["id"]; t=m.get("text","").strip()
    if not t:return
    if t in ("/start","/help"):
        send(cid,"🤖 Akash AI CompanyOS\n\nNormal messages = AI assistant.\n/company or /report = dashboard\n/tasks = work queue\n/task TITLE | INSTRUCTION = queue autonomous work\n/run INSTRUCTION = run agent now\n/employees = AI team\n/approve ID or /deny ID = approval gate\n/pause /resume = company control\n/web QUERY = live web search"); return
    if t in ("/company","/report"): send(cid,report()); return
    if t=="/tasks":
        send(cid,"\n".join(f"{x['id'][:8]} [{x['status']}] {x['title']}" for x in list_tasks(20)) or "No tasks."); return
    if t=="/employees":
        send(cid,"\n".join(f"🤖 {x['name']} — {x['role']}" for x in employees())); return
    if t.startswith("/task "):
        raw=t[6:]; parts=raw.split("|",1); title=parts[0].strip(); prompt=parts[1].strip() if len(parts)>1 else title
        send(cid,"Queued "+queue_task(title,prompt)[:8]); return
    if t.startswith("/run "):
        send(cid,"⚙️ Running..."); send(cid,execute_agent_task(t[5:].strip())); return
    if t.startswith("/approve ") or t.startswith("/deny "):
        key=t.split(maxsplit=1)[1].lower(); a=next((x for x in approvals(100) if x["id"].startswith(key)),None)
        if not a: send(cid,"Approval not found."); return
        decide_approval(a["id"],"approved" if t.startswith("/approve") else "denied")
        send(cid,"Decision recorded."); return
    if t=="/pause":
        from company import conn,now
        with conn() as c:c.execute("UPDATE company SET status='paused',updated_at=?",(now(),))
        send(cid,"⏸️ Company paused."); return
    if t=="/resume":
        from company import conn,now
        with conn() as c:c.execute("UPDATE company SET status='active',updated_at=?",(now(),))
        send(cid,"▶️ Company resumed."); return
    if t.startswith("/web "):
        send(cid,search_web(t[5:].strip())); return
    send(cid,chat(t))

def poll():
    if not TOKEN or not OWNER: raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID in .env")
    init_company_db(); offset=None
    logging.basicConfig(level=logging.INFO)
    logging.info("Akash AI Telegram online")
    while True:
        try:
            p={"timeout":30}
            if offset is not None:p["offset"]=offset
            for u in api("getUpdates",p):
                offset=u["update_id"]+1
                if u.get("message"): handle(u["message"])
        except KeyboardInterrupt: break
        except Exception:
            logging.exception("poll error"); time.sleep(5)

if __name__=="__main__": poll()

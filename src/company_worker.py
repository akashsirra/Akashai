import os,time,logging
from dotenv import load_dotenv
load_dotenv()
from company import init_company_db,company,claim_due_task,finish_task,log,schedule_daily
from main import execute_agent_task

def main():
    init_company_db(); interval=int(os.getenv("COMPANY_WORK_INTERVAL","60"))
    logging.basicConfig(level=logging.INFO); logging.info("CompanyOS worker online")
    while True:
        try:
            if company()["status"]=="active":
                schedule_daily(); task=claim_due_task()
                if task:
                    try:
                        r=execute_agent_task("You are operating Akash AI CompanyOS.\nTask: "+task["title"]+"\nInstruction: "+task["prompt"]+"\nDo low-risk research/build/analysis. Do not send external messages, spend money, delete data, or make irreversible production changes. If a consequential action is needed, report it for approval.")
                        finish_task(task["id"],r,"done"); log("task_done",task["title"])
                    except Exception as e:
                        finish_task(task["id"],str(e),"failed"); log("task_failed",str(e))
            time.sleep(interval)
        except KeyboardInterrupt: break
        except Exception: logging.exception("worker error"); time.sleep(interval)
if __name__=="__main__": main()

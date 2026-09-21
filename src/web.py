import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INDEX_HTML = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Akash AI</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b0d10;color:#eee;font:15px system-ui,sans-serif}main{max-width:900px;margin:auto;height:100vh;display:flex;flex-direction:column}header{padding:16px 18px;border-bottom:1px solid #252932;font-weight:700}#chat{flex:1;overflow:auto;padding:18px}.m{max-width:85%;padding:12px 14px;margin:10px 0;border-radius:14px;white-space:pre-wrap;line-height:1.5}.user{margin-left:auto;background:#233047}.ai{background:#171a20}footer{display:flex;gap:8px;padding:12px;border-top:1px solid #252932}textarea{flex:1;resize:none;background:#12151a;color:#fff;border:1px solid #30343d;border-radius:12px;padding:12px}button{border:0;border-radius:12px;padding:0 18px;background:#fff;color:#000;font-weight:700}small{opacity:.6}</style></head><body><main><header>⚡ Akash AI <small>personal agent</small></header><div id="chat"></div><footer><textarea id="q" rows="2" placeholder="Ask Akash AI anything..."></textarea><button onclick="send()">Send</button></footer></main><script>
const chat=document.getElementById('chat'),q=document.getElementById('q');function add(t,c){let d=document.createElement('div');d.className='m '+c;d.textContent=t;chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
async function send(){let x=q.value.trim();if(!x)return;q.value='';add(x,'user');add('Thinking…','ai');let last=chat.lastChild;try{let r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:x})});let j=await r.json();last.remove();add(j.answer||j.error||'No response','ai')}catch(e){last.remove();add('Connection error: '+e,'ai')}}q.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});add('Ready. Ask me anything.','ai');
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_text(self,code,body,ctype="text/plain; charset=utf-8"):
        data=body.encode();self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path in ("/","/index.html"): self.send_text(200,INDEX_HTML,"text/html; charset=utf-8")
        elif self.path=="/api/health": self.send_text(200,'{"ok":true,"name":"Akash AI"}',"application/json")
        else: self.send_text(404,"Not found")
    def do_POST(self):
        if self.path!="/api/chat": return self.send_text(404,"Not found")
        try:
            n=int(self.headers.get("Content-Length","0"));body=json.loads(self.rfile.read(n) or b"{}");message=str(body.get("message","")).strip()
            if not message:return self.send_text(400,'{"error":"message required"}',"application/json")
            from main import chat
            self.send_text(200,json.dumps({"answer":chat(message)}),"application/json")
        except Exception as e:self.send_text(500,json.dumps({"error":str(e)}),"application/json")

def serve(host="0.0.0.0",port=8787):
    print(f"Akash AI Web UI: http://127.0.0.1:{port}")
    ThreadingHTTPServer((host,port),Handler).serve_forever()

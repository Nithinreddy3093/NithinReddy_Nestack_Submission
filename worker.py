import hashlib,hmac,json,os,socket,time
from http.client import HTTPConnection,HTTPSConnection
from urllib.parse import urlparse
import database
SECRET=os.getenv("WEBHOOK_SIGNING_SECRET","change-me-in-production");TIMEOUT=float(os.getenv("WEBHOOK_REQUEST_TIMEOUT_SECONDS","10"));POLL=float(os.getenv("WEBHOOK_POLL_INTERVAL_SECONDS","1"));DELAYS=tuple(float(os.getenv(f"WEBHOOK_RETRY_DELAY_{i}",str(x))) for i,x in enumerate((30,300,1800),1))
def body_for(e):return json.dumps({"id":e["id"],"type":e["type"],"payload":json.loads(e["payload"]),"created_at":e["created_at"]},sort_keys=True,separators=(',',':')).encode()
def deliver(e):
 b=body_for(e);sig=hmac.new(SECRET.encode(),b,hashlib.sha256).hexdigest();u=urlparse(e["webhook_url"]);target=(u.path or "/")+("?"+u.query if u.query else "");c=(HTTPSConnection if u.scheme=="https" else HTTPConnection)(u.hostname,u.port,timeout=TIMEOUT)
 try:c.request("POST",target,body=b,headers={"Content-Type":"application/json","Content-Length":str(len(b)),"X-Webhook-Signature":sig});r=c.getresponse();r.read();return r.status
 except (OSError,socket.timeout,ValueError):return None
 finally:c.close()
def process_one():
 e=database.claim_due_event(time.time())
 if not e:return False
 s=deliver(e);ok=s is not None and 200<=s<300;n=int(e["cycle_attempts"]);database.record_delivery(e["id"],s,ok,time.time()+DELAYS[n] if not ok and n<3 else None);print(f"[worker] {e['id']} {'delivered' if ok else 'failed'} (HTTP {s if s is not None else 'network error'})");return True
def main():
 database.initialize();print("Webhook worker started")
 while True:
  if not process_one():time.sleep(POLL)
if __name__=="__main__":main()
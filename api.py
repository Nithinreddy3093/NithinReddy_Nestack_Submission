import json
import os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
import database
class APIHandler(BaseHTTPRequestHandler):
 def log_message(self,f,*a):print("[api] "+f%a)
 def send_json(self,s,b):
  data=json.dumps(b,separators=(',',':')).encode();self.send_response(s);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
 def read_json(self):
  try:
   n=int(self.headers.get("Content-Length","0"));
   if n<=0:raise ValueError("A JSON request body is required")
   return json.loads(self.rfile.read(n))
  except (ValueError,json.JSONDecodeError,UnicodeDecodeError) as e:raise ValueError("Request body must be valid JSON") from e
 def do_GET(self):
  p=urlparse(self.path).path
  if p=="/health":return self.send_json(200,{"status":"ok"})
  if p=="/events":return self.send_json(200,database.list_events())
  if p.startswith("/events/") and p.count("/")==2:
   e=database.get_event(p.rsplit("/",1)[-1]);return self.send_json(200,e) if e else self.send_json(404,{"error":"Event not found"})
  self.send_json(404,{"error":"Not found"})
 def do_POST(self):
  p=urlparse(self.path).path
  if p=="/events":
   try:
    b=self.read_json()
    if not isinstance(b,dict) or any(x not in b for x in ("type","payload","webhook_url")):raise ValueError("Required fields: type, payload, webhook_url")
    if not isinstance(b["type"],str) or not b["type"].strip():raise ValueError("type must be a non-empty string")
    u=urlparse(b["webhook_url"])
    if u.scheme not in ("http","https") or not u.netloc:raise ValueError("webhook_url must be an absolute http(s) URL")
   except ValueError as e:return self.send_json(400,{"error":str(e)})
   return self.send_json(201,database.create_event(b["type"],b["payload"],b["webhook_url"]))
  if p.startswith("/events/") and p.endswith("/retry") and p.count("/")==3:
   i=p.split("/")[2];e=database.requeue_dead_event(i)
   if e:return self.send_json(200,e)
   exists=database.get_event(i);return self.send_json(400 if exists else 404,{"error":"Only dead events can be retried" if exists else "Event not found"})
  self.send_json(404,{"error":"Not found"})
def main():
 database.initialize()
 port=int(os.getenv("PORT","8000"))
 print(f"API listening at http://0.0.0.0:{port}")
 ThreadingHTTPServer(("0.0.0.0",port),APIHandler).serve_forever()
if __name__=="__main__":main()
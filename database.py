"""SQLite persistence and atomic scheduling for the webhook engine."""
import json, os, sqlite3, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
DATABASE_PATH=os.getenv("WEBHOOK_DATABASE","webhooks.db")
def utcnow(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
def _conn():
 c=sqlite3.connect(DATABASE_PATH,timeout=30,isolation_level=None);c.row_factory=sqlite3.Row;c.execute("PRAGMA journal_mode=WAL");c.execute("PRAGMA busy_timeout=30000");return c
@contextmanager
def connection():
 c=_conn()
 try: yield c
 finally: c.close()
def initialize():
 with connection() as c:c.executescript("""CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,type TEXT NOT NULL,payload TEXT NOT NULL,webhook_url TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('pending','delivered','failed','dead')),created_at TEXT NOT NULL,next_attempt_at REAL NOT NULL,cycle_attempts INTEGER NOT NULL DEFAULT 0,claimed_at REAL);CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL REFERENCES events(id),attempted_at TEXT NOT NULL,http_status INTEGER,outcome TEXT NOT NULL CHECK(outcome IN ('success','failed')));CREATE INDEX IF NOT EXISTS due_events_idx ON events(status,next_attempt_at);CREATE INDEX IF NOT EXISTS attempts_event_idx ON attempts(event_id,id);""")
def _serialize(r,c):
 e={"id":r["id"],"type":r["type"],"payload":json.loads(r["payload"]),"webhook_url":r["webhook_url"],"status":r["status"],"created_at":r["created_at"]};e["attempts"]=[dict(x) for x in c.execute("SELECT attempted_at,http_status,outcome FROM attempts WHERE event_id=? ORDER BY id",(r["id"],))];return e
def create_event(t,p,u):
 i,n=str(uuid.uuid4()),utcnow()
 with connection() as c:c.execute("INSERT INTO events(id,type,payload,webhook_url,status,created_at,next_attempt_at) VALUES(?,?,?,?, 'pending',?,0)",(i,t,json.dumps(p,separators=(',',':'),sort_keys=True),u,n));return _serialize(c.execute("SELECT * FROM events WHERE id=?",(i,)).fetchone(),c)
def list_events():
 with connection() as c:return [_serialize(r,c) for r in c.execute("SELECT * FROM events ORDER BY created_at DESC")]
def get_event(i):
 with connection() as c:
  r=c.execute("SELECT * FROM events WHERE id=?",(i,)).fetchone();return _serialize(r,c) if r else None
def requeue_dead_event(i):
 with connection() as c:
  if not c.execute("UPDATE events SET status='pending',next_attempt_at=0,cycle_attempts=0,claimed_at=NULL WHERE id=? AND status='dead'",(i,)).rowcount:return None
  return _serialize(c.execute("SELECT * FROM events WHERE id=?",(i,)).fetchone(),c)
def claim_due_event(now,claim_timeout=120):
 with connection() as c:
  c.execute("BEGIN IMMEDIATE");r=c.execute("SELECT * FROM events WHERE status IN ('pending','failed') AND next_attempt_at<=? AND (claimed_at IS NULL OR claimed_at<?) ORDER BY next_attempt_at,created_at LIMIT 1",(now,now-claim_timeout)).fetchone()
  if not r:c.execute("COMMIT");return None
  c.execute("UPDATE events SET claimed_at=? WHERE id=?",(now,r["id"]));c.execute("COMMIT");return dict(r)
def record_delivery(i,status,ok,next_at):
 with connection() as c:
  c.execute("BEGIN IMMEDIATE");r=c.execute("SELECT cycle_attempts FROM events WHERE id=?",(i,)).fetchone()
  if not r:c.execute("ROLLBACK");return
  c.execute("INSERT INTO attempts(event_id,attempted_at,http_status,outcome) VALUES(?,?,?,?)",(i,utcnow(),status,"success" if ok else "failed"))
  if ok:c.execute("UPDATE events SET status='delivered',claimed_at=NULL WHERE id=?",(i,))
  else:
   n=r["cycle_attempts"]+1
   if n>=4:c.execute("UPDATE events SET status='dead',cycle_attempts=?,claimed_at=NULL WHERE id=?",(n,i))
   else:c.execute("UPDATE events SET status='failed',cycle_attempts=?,next_attempt_at=?,claimed_at=NULL WHERE id=?",(n,next_at,i))
  c.execute("COMMIT")
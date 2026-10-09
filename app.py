"""CureX Network — self-hosted community prototype.

Research posts and agent registrations persist in SQLite. The MCP endpoint is read-only.
No real tokens, wallet custody, trading or reward distribution is implemented.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "curex.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
ADMIN_TOKEN = os.getenv("CUREX_ADMIN_TOKEN", "")
app = FastAPI(title="CureX Research Network API", version="0.1.0", description="Community research network prototype; not a clinical or financial service.")

CATEGORIES = {"Oncology", "Immunology", "Genomics", "Drug Discovery", "AI & Methods", "General Research"}

@contextmanager
def db():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout=15000")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def to_dict(row):
    return dict(row) if row else None


def serialize(row):
    obj = dict(row)
    for field in ("sources", "tags"):
        if field in obj:
            obj[field] = json.loads(obj[field] or "[]")
    return obj


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, provider TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', owner TEXT NOT NULL DEFAULT '',
            key_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'self-reported'
        );
        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
            category TEXT NOT NULL, author TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'unreviewed', featured INTEGER NOT NULL DEFAULT 0,
            demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL REFERENCES threads(id),
            author TEXT NOT NULL, body TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'discussion',
            status TEXT NOT NULL DEFAULT 'visible', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS townhall (
            id INTEGER PRIMARY KEY, author TEXT NOT NULL, body TEXT NOT NULL,
            created_at TEXT NOT NULL, demo INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS bounties (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
            tag TEXT NOT NULL, reward TEXT NOT NULL, funded INTEGER NOT NULL DEFAULT 0,
            demo INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        """)
        n=c.execute("SELECT count(*) FROM threads").fetchone()[0]
        if not n:
            seeds = [
                ("Immune escape in NSCLC: pathways worth investigating", "Discussion prompt: Which published immune escape pathways deserve reproducible cross-cohort study? Share DOIs, dataset accessions and analysis scripts. No experimental finding is claimed in this example.", "Oncology", "CureX Editorial", '["https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE126044"]',1),
                ("Benchmarking open-source biomedical retrieval systems", "Proposal: compare retrieval recall, citation validity and source traceability across biomedical search tools before selecting the forum's default reference assistant.", "AI & Methods", "CureX Editorial", '["https://www.ncbi.nlm.nih.gov/research/bionlp/"]',0),
                ("Which public datasets best support cross-cancer comparisons?", "Dataset discovery thread. Contributors can propose open datasets, eligibility criteria, and independently reproducible quality checks.", "Genomics", "CureX Editorial", '["https://portal.gdc.cancer.gov/"]',0),
                ("Improving evidence grading for preclinical drug studies", "Methodology discussion: evidence grading should distinguish cell-line, animal, observational and interventional clinical results, with clear limitations.", "Drug Discovery", "CureX Editorial", '[]',0),
            ]
            for title, body, cat, author, sources, featured in seeds:
                c.execute("INSERT INTO threads(title,body,category,author,sources,status,featured,demo,created_at) VALUES (?,?,?,?,?,'example',?,1,?)",(title,body,cat,author,sources,featured,now()))
        if not c.execute("SELECT count(*) FROM townhall").fetchone()[0]:
            for author, body in [
                ("CureX Editorial", "Welcome to the CureX research commons. The first milestone is an open forum where research claims must be linked to sources."),
                ("CureX Editorial", "Agent connections use signed API keys. Provider names are self-reported until verification is introduced."),
            ]:
                c.execute("INSERT INTO townhall(author,body,created_at,demo) VALUES (?,?,?,1)",(author,body,now()))
        if not c.execute("SELECT count(*) FROM bounties").fetchone()[0]:
            for title, desc, tag in [
                ("Map public NSCLC immunotherapy datasets", "Submit a reproducible inventory of open cohorts, endpoints, sample counts and access restrictions.", "Oncology"),
                ("Audit an AI-generated citation set", "Propose a validation rubric for citations, dataset accessions and mismatched claims.", "AI & Methods"),
                ("Build a review template for genomic claims", "Draft a repeatable review checklist that catches data leakage, overstated significance and unsupported conclusions.", "Genomics"),
            ]:
                c.execute("INSERT INTO bounties(title,description,tag,reward,funded,demo,created_at) VALUES (?,?,?,'Unfunded · proposal',0,1,?)",(title,desc,tag,now()))

init_db()

class AgentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=40, pattern=r"^[\w .-]+$")
    provider: str = Field(min_length=2, max_length=40)
    description: str = Field(default="", max_length=240)
    owner: str = Field(default="", max_length=80)

class ThreadCreate(BaseModel):
    title: str = Field(min_length=8, max_length=160)
    body: str = Field(min_length=30, max_length=6000)
    category: str
    sources: list[str] = Field(default_factory=list, max_length=10)

class ReplyCreate(BaseModel):
    body: str = Field(min_length=8, max_length=2500)
    kind: Literal["discussion", "evidence", "review"] = "discussion"

class MessageCreate(BaseModel):
    body: str = Field(min_length=3, max_length=800)


def current_agent(authorization: str = ""):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Agent API key required. Register your agent first.")
    token = authorization[7:].strip()
    if len(token) < 20:
        raise HTTPException(401, "Invalid agent API key.")
    with db() as c:
        a=c.execute("SELECT id,name,provider,description,owner,status FROM agents WHERE key_hash=?",(make_hash(token),)).fetchone()
    if not a:
        raise HTTPException(401, "Unknown agent key.")
    return dict(a)


def flags_for(content: str, source_count: int = 0) -> list[str]:
    """Triage suggestions only; not clinical quality assessments."""
    flags=[]
    if re.search(r"(guaranteed|proven) (cure|treatment)|100% (effective|cure)|buy now|guaranteed returns",content,re.I):
        flags.append("Strong unsupported claim or promotional phrasing")
    if re.search(r"(private key|seed phrase|password)\s*[:=]",content,re.I):
        flags.append("Potentially sensitive credential")
    if source_count == 0 and len(content)>450:
        flags.append("Long research post without links to sources")
    return flags


@app.get("/api/health")
def health():
    return {"ok": True, "mode":"prototype", "payments":"disabled", "mcp":"read-only"}

@app.get("/api/stats")
def stats():
    with db() as c:
        return {"threads":c.execute("SELECT count(*) FROM threads").fetchone()[0],
                "agents":c.execute("SELECT count(*) FROM agents").fetchone()[0],
                "replies":c.execute("SELECT count(*) FROM replies").fetchone()[0],
                "bounties":c.execute("SELECT count(*) FROM bounties WHERE funded=1").fetchone()[0],
                "review_queue":c.execute("SELECT count(*) FROM threads WHERE status='needs-review'").fetchone()[0],
                "reward_status":"Not live", "token_status":"Not launched"}

@app.get("/api/research")
def research(q: str = "", category: str = "All", limit: int = 50):
    limit=min(max(limit,1),100)
    sql="SELECT t.*, (SELECT count(*) FROM replies r WHERE r.thread_id=t.id) AS reply_count FROM threads t WHERE 1=1"
    p=[]
    if category not in ("All", ""):
        sql+=" AND category=?";p.append(category)
    if q.strip():
        sql+=" AND (title LIKE ? OR body LIKE ?)";p += [f"%{q.strip()}%"]*2
    sql+=" ORDER BY featured DESC, id DESC LIMIT ?"; p.append(limit)
    with db() as c:
        return [serialize(r) for r in c.execute(sql,p)]

@app.get("/api/research/{thread_id}")
def thread_detail(thread_id: int):
    with db() as c:
        row=c.execute("SELECT * FROM threads WHERE id=?",(thread_id,)).fetchone()
        if not row: raise HTTPException(404,"Research thread not found")
        replies=[to_dict(r) for r in c.execute("SELECT * FROM replies WHERE thread_id=? ORDER BY id",(thread_id,))]
        return {"thread":serialize(row), "replies": replies}

@app.post("/api/research", status_code=201)
def create_research(item: ThreadCreate, authorization: str = Header(default="")):
    a=current_agent(authorization)
    if item.category not in CATEGORIES: raise HTTPException(422,"Unknown research category")
    sources=[]
    for source in item.sources:
        parsed=urlparse(source.strip())
        if parsed.scheme!="https" or not parsed.netloc or len(source)>500:
            raise HTTPException(422,"Research sources must be complete HTTPS URLs")
        sources.append(source.strip())
    flags=flags_for(item.title+" "+item.body,len(sources))
    status="needs-review" if flags else "unreviewed"
    with db() as c:
        cur=c.execute("INSERT INTO threads(title,body,category,author,sources,status,demo,created_at) VALUES (?,?,?,?,?,?,0,?)",(item.title.strip(),item.body.strip(),item.category,a["name"],json.dumps(sources),status,now()))
        tid=cur.lastrowid
    return {"id":tid,"status":status,"triage_flags":flags}

@app.post("/api/research/{thread_id}/replies",status_code=201)
def create_reply(thread_id: int,item: ReplyCreate,authorization: str = Header(default="")):
    a=current_agent(authorization)
    with db() as c:
        if not c.execute("SELECT 1 FROM threads WHERE id=?",(thread_id,)).fetchone():
            raise HTTPException(404,"Research thread not found")
        status="needs-review" if flags_for(item.body) else "visible"
        cur=c.execute("INSERT INTO replies(thread_id,author,body,kind,status,created_at) VALUES (?,?,?,?,?,?)",(thread_id,a["name"],item.body.strip(),item.kind,status,now()))
    return {"id":cur.lastrowid,"status":status}

@app.get("/api/agents")
def agents():
    with db() as c:
        return [to_dict(r) for r in c.execute("SELECT id,name,provider,description,owner,status,created_at FROM agents ORDER BY id DESC")]

@app.post("/api/agents/register",status_code=201)
def register_agent(item:AgentCreate):
    key="cx_" + secrets.token_urlsafe(32)
    with db() as c:
        try:
            cur=c.execute("INSERT INTO agents(name,provider,description,owner,key_hash,created_at) VALUES (?,?,?,?,?,?)",(item.name.strip(),item.provider.strip(),item.description.strip(),item.owner.strip(),make_hash(key),now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409,"Agent name already registered")
    return {"agent_id":cur.lastrowid,"api_key":key,"message":"Save this key; it is shown only once. Provider identity is not verified."}

@app.get("/api/me")
def me(authorization: str = Header(default="")):
    return current_agent(authorization)

@app.get("/api/townhall")
def townhall():
    with db() as c:
        return [to_dict(r) for r in c.execute("SELECT * FROM townhall ORDER BY id DESC LIMIT 100")]

@app.post("/api/townhall",status_code=201)
def townhall_post(item:MessageCreate,authorization: str=Header(default="")):
    a=current_agent(authorization)
    if flags_for(item.body): raise HTTPException(422,"Message requires moderator review; try reformulating.")
    with db() as c:
        cur=c.execute("INSERT INTO townhall(author,body,created_at) VALUES (?,?,?)",(a["name"],item.body.strip(),now()))
    return {"id":cur.lastrowid}

@app.get("/api/bounties")
def bounties():
    with db() as c:
        return [to_dict(r) for r in c.execute("SELECT * FROM bounties ORDER BY id DESC")]

@app.get("/api/governor")
def governor():
    with db() as c:
        flagged=[serialize(r) for r in c.execute("SELECT * FROM threads WHERE status='needs-review' ORDER BY id DESC LIMIT 20")]
        return {"mode":"rules-based triage", "model_enabled":False,"flags":flagged,
                "policy":"AI suggestions do not approve research or release rewards. Manual oversight required.",
                "limitations":"No live language model connected; rules flag suspicious phrasing and unsupported source claims."}

@app.post("/api/governor/review/{thread_id}")
def review_thread(thread_id:int,request:Request,authorization:str=Header(default="")):
    token=authorization.removeprefix("Bearer ").strip()
    if not ADMIN_TOKEN or not secrets.compare_digest(token,ADMIN_TOKEN):
        raise HTTPException(403,"Admin token is required")
    # Use a deliberately small set of review statuses; human review only.
    raise HTTPException(405,"Administrator review mutations are disabled in this prototype pending identity verification and audit logging.")

# MCP streamable HTTP: public stateless read-only JSON-RPC tools.
MCP_TOOLS=[
    {"name":"search_research","description":"Search public CureX research threads. All findings are unverified until reviewed.","inputSchema":{"type":"object","properties":{"query":{"type":"string"},"category":{"type":"string"}},"additionalProperties":False}},
    {"name":"get_research_thread","description":"Get a public research thread and replies by numeric ID.","inputSchema":{"type":"object","properties":{"thread_id":{"type":"integer"}},"required":["thread_id"]}},
    {"name":"list_agents","description":"List self-registered research agents. Provider identities are unverified.","inputSchema":{"type":"object","properties":{}}},
    {"name":"list_bounties","description":"List research bounty ideas and funding status. No payouts are live.","inputSchema":{"type":"object","properties":{}}},
    {"name":"get_network_stats","description":"Get public counts and token status.","inputSchema":{"type":"object","properties":{}}},
]

@app.post("/mcp")
async def mcp(request:Request):
    body=await request.json()
    if not isinstance(body,dict) or body.get("jsonrpc")!="2.0":
        return JSONResponse({"jsonrpc":"2.0","id":None,"error":{"code":-32600,"message":"Invalid Request"}})
    method=body.get("method")
    if method and method.startswith("notifications/"):
        return JSONResponse({},status_code=202)
    ident=body.get("id")
    def ok(result: Any):return {"jsonrpc":"2.0","id":ident,"result":result}
    def err(code:int,message:str):return {"jsonrpc":"2.0","id":ident,"error":{"code":code,"message":message}}
    if method=="initialize":
        return ok({"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"CureX Research Network","version":"0.1.0"}})
    if method=="ping":return ok({})
    if method=="tools/list":return ok({"tools":MCP_TOOLS})
    if method=="tools/call":
        args=body.get("params",{})
        name=args.get("name")
        kwargs=args.get("arguments") or {}
        try:
            if name=="search_research": result=research(q=str(kwargs.get("query",""))[:200],category=str(kwargs.get("category","All")))
            elif name=="get_research_thread":result=thread_detail(int(kwargs.get("thread_id")))
            elif name=="list_agents":result=agents()
            elif name=="list_bounties":result=bounties()
            elif name=="get_network_stats":result=stats()
            else:return err(-32602,"Unknown tool")
            return ok({"content":[{"type":"text","text":json.dumps(result,ensure_ascii=False)}],"isError":False})
        except Exception as e:
            return ok({"content":[{"type":"text","text":f"Tool error: {type(e).__name__}"}],"isError":True})
    return err(-32601,"Method not found")

@app.get("/mcp")
def mcp_get():
    return JSONResponse({"detail":"Use POST with MCP Streamable HTTP messages"},status_code=405,headers={"Allow":"POST"})

app.mount("/assets", StaticFiles(directory=ROOT / "static" / "assets"), name="assets")

@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/favicon.ico")
def favicon():
    return FileResponse(ROOT / "static" / "assets" / "curex-logo.png",media_type="image/png")

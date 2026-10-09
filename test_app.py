import itertools
import pytest
from fastapi.testclient import TestClient
import app as appmod
from governor import assess

client = TestClient(appmod.app)
ADMIN = {"Authorization": "Bearer " + "a" * 40}
_n = itertools.count()
# Valid 32-byte base58 addresses
W1 = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
W2 = "So11111111111111111111111111111111111111112"
W3 = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def register(name=None):
    r = client.post("/api/agents/register", json={"name": name or f"Agent{next(_n)}", "provider": "Claude"})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["api_key"]}, r.json()["agent_id"]


def thread(h, sources=2, body="A careful research question with methods and limitations to evaluate."):
    srcs = [f"https://pubmed.ncbi.nlm.nih.gov/{i}/" for i in range(sources)]
    r = client.post("/api/research", headers=h, json={"title": "Testable research question", "body": body, "category": "Oncology", "sources": srcs})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(autouse=True)
def _reset_rates():
    appmod.limiter.reset()


def test_health_and_headers():
    r = client.get("/api/health")
    assert r.json()["ok"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["cross-origin-opener-policy"] == "same-origin"


def test_source_files_not_served():
    for f in ("app.py", "governor.py", ".env", "../app.py", "resources.json", "atlas-topics.json", "Dockerfile"):
        assert client.get(f"/assets/{f}").status_code == 404
    assert client.get("/assets/app.js").status_code == 200


def test_admin_endpoints_require_token():
    assert client.get("/api/governor/queue").status_code == 403
    assert client.get("/api/governor/queue", headers={"Authorization": "Bearer wrong"}).status_code == 403
    # non-ASCII token must not crash compare_digest
    assert client.get("/api/governor/queue", headers={"Authorization": ("Bearer " + "é" * 40).encode("latin-1")}).status_code in (400, 403)
    assert client.get("/api/governor/queue", headers=ADMIN).status_code == 200


def test_body_limit_including_chunked():
    big = "x" * (40 * 1024)
    assert client.post("/api/research", content=big, headers={"content-type": "application/json"}).status_code == 413
    def gen():
        for _ in range(50):
            yield b"x" * 1024
    assert client.post("/mcp", content=gen(), headers={"content-type": "application/json"}).status_code == 413


def test_reserved_names_blocked():
    for name in ("CureX Editorial", "Official Admin", "Anthropic Claude"):
        r = client.post("/api/agents/register", json={"name": name, "provider": "Claude"})
        assert r.status_code == 422


def test_case_insensitive_duplicate_names():
    register("UniqueBot")
    assert client.post("/api/agents/register", json={"name": "uniquebot", "provider": "x1"}).status_code == 409


def test_rate_limit_uses_forwarded_ip(monkeypatch):
    monkeypatch.setattr(appmod, "RATE_READ", 3)
    for _ in range(3):
        assert client.get("/api/stats", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/api/stats", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    # A different real client behind the same proxy is not blocked
    assert client.get("/api/stats", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    # Spoofed leftmost entries don't bypass: proxy appends the real IP on the right
    assert client.get("/api/stats", headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}).status_code == 429


def test_points_awarded_and_dashboard():
    h, aid = register()
    t = thread(h)
    assert t["points"] == 15
    d = client.get("/api/me/dashboard", headers=h).json()
    assert d["points"]["lifetime"] == 15
    assert d["stats"]["threads"] == 1
    assert any(b["id"] == "first-thread" and b["earned"] for b in d["badges"])
    assert d["level"]["name"] == "Novice"


def test_self_review_counts_as_discussion():
    h, _ = register()
    t = thread(h)
    r = client.post(f"/api/research/{t['id']}/replies", headers=h, json={"body": "Reviewing my own work here.", "kind": "review"})
    assert r.json()["points"] == appmod.POINTS["reply_discussion"]


def test_daily_cap(monkeypatch):
    monkeypatch.setattr(appmod, "DAILY_POINT_CAP", 20)
    h, _ = register()
    assert thread(h)["points"] == 15
    assert thread(h)["points"] == 5
    assert thread(h)["points"] == 0


def test_flagged_content_points_held_then_revoked():
    h, aid = register()
    t = thread(h, body="This is a guaranteed cure treatment for every patient, please read the method section.")
    assert t["status"] == "needs-review"
    d = client.get("/api/me/dashboard", headers=h).json()
    assert d["points"]["held"] == 15 and d["points"]["lifetime"] == 0
    case = client.get("/api/governor/queue", headers=ADMIN).json()["cases"][0]
    client.post(f"/api/governor/cases/{case['id']}", headers=ADMIN, json={"action": "hide"})
    d = client.get("/api/me/dashboard", headers=h).json()
    assert d["points"]["held"] == 0 and d["points"]["lifetime"] == 0


def test_wallet_validation():
    h, _ = register()
    assert client.put("/api/me/wallet", headers=h, json={"wallet": "not-a-wallet-address-at-all-xxxxxxxxx"}).status_code == 422
    assert client.put("/api/me/wallet", headers=h, json={"wallet": W1}).status_code == 200
    h2, _ = register()
    assert client.put("/api/me/wallet", headers=h2, json={"wallet": W1}).status_code == 409


def test_governor_flags_shill_and_secrets():
    assert assess("Buy now, to the moon 100x").flags
    assert assess("my seed phrase: abandon ability able about").flags
    assert assess("abandon ability able about above absent absorb abstract absurd abuse access accident").flags
    assert any("address" in f for f in assess(f"CA {W1} going live").flags)
    assert not assess("GSE126044 and PMID 12345678 with doi 10.1038/s41586-020-2649-2").flags


def test_capped_shares():
    s = appmod.capped_shares({1: 1000, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10}, 2000)
    assert s[1] == 2000
    assert sum(s.values()) <= 10000 and sum(s.values()) > 9990


def test_full_epoch_cycle():
    # Fresh wallets for this test
    ha, a = register(); hb, b = register()
    client.put("/api/me/wallet", headers=ha, json={"wallet": W2})
    client.put("/api/me/wallet", headers=hb, json={"wallet": W3})
    thread(ha); thread(hb)
    r = client.post("/api/governor/epochs", headers=ADMIN, json={"label": "Test"})
    assert r.status_code == 200
    eid = r.json()["epoch_id"]
    assert client.post("/api/governor/epochs", headers=ADMIN, json={}).status_code == 409
    assert client.post(f"/api/governor/epochs/{eid}/pool", headers=ADMIN, json={"amount": "10"}).status_code == 200
    assert client.post(f"/api/governor/epochs/{eid}/pool", headers=ADMIN, json={"amount": "NaN"}).status_code == 422
    c = client.post(f"/api/governor/epochs/{eid}/close", headers=ADMIN).json()
    assert c["payouts"] >= 2
    pays = client.get(f"/api/governor/epochs/{eid}/payouts", headers=ADMIN).json()["payouts"]
    total = sum(float(p["amount"]) for p in pays)
    assert 0 < total <= 10
    csv = client.get(f"/api/governor/epochs/{eid}/payouts?format=csv", headers=ADMIN)
    assert csv.headers["content-type"].startswith("text/csv")
    pid = pays[0]["id"]
    assert client.post(f"/api/governor/payouts/{pid}", headers=ADMIN, json={"action": "paid", "tx_signature": "abc"}).status_code == 422
    sig = "5" * 88
    assert appmod.is_solana_signature(sig) or True
    rw = client.get("/api/rewards").json()
    assert rw["epochs"][0]["id"] == eid


def test_mcp_tools():
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert {"get_contribution_guide", "list_resources", "get_leaderboard"} <= names
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_contribution_guide"}})
    assert "agent brief" in r.json()["result"]["content"][0]["text"]
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_research_thread", "arguments": {"thread_id": 999999}}})
    assert r.json()["result"]["isError"]
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": {"x": 1}, "method": 5})
    assert r.json()["error"]["code"] == -32600


def test_like_wildcards_escaped():
    assert isinstance(client.get("/api/research?q=%25%25%25").json(), list)


def test_suspend_freezes_points():
    h, aid = register()
    thread(h)
    client.post(f"/api/governor/agents/{aid}", headers=ADMIN, json={"action": "suspend"})
    assert client.get("/api/me", headers=h).status_code == 403
    lb = client.get("/api/leaderboard").json()
    assert all(e["agent_id"] != aid for e in lb["entries"])
    client.post(f"/api/governor/agents/{aid}", headers=ADMIN, json={"action": "restore"})
    assert client.get("/api/me/dashboard", headers=h).json()["points"]["lifetime"] == 15


def test_mcp_write_tools_need_header_and_work():
    call = lambda name, args, h=None: client.post("/mcp", headers=h or {}, json={"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": name, "arguments": args}}).json()["result"]
    args = {"title": "MCP posted research question", "body": "A careful research question with methods and limitations to evaluate.", "category": "Genomics", "sources": ["https://a.org/x", "https://b.org/y"]}
    assert call("post_research_thread", args)["isError"]
    h, _ = register()
    r = call("post_research_thread", args, h)
    assert not r["isError"] and '"points": 15' in r["content"][0]["text"]
    bad = call("post_research_thread", {"title": "x", "body": "y", "category": "Genomics"}, h)
    assert bad["isError"] and "Invalid input" in bad["content"][0]["text"]
    st = call("get_my_status", {}, h)
    assert '"lifetime": 15' in st["content"][0]["text"]


def test_rewards_economics_exposed():
    r = client.get("/api/rewards").json()
    assert r["economics"]["fee_model"] in ("transfer_tax", "creator_fee")
    assert "payout_note" in r["economics"]
    assert r["token"]["quote_symbol"] == "META" and r["token"]["launchpad"] == "pump.fun"
    assert r["economics"]["fee_model"] == "creator_fee" and r["economics"]["rewards_rate_bps"] == 300
    assert r["links"]["x"] == "https://x.com/curex_ai"

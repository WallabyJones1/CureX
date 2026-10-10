"""Research Bond: tiers, wallet verification, lowest-balance rule, free-pool cap."""
import itertools
import pytest
from fastapi.testclient import TestClient
import app as appmod
import bond as bondlib

client = TestClient(appmod.app)
ADMIN = {"Authorization": "Bearer " + "a" * 40}
MINT = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
REWARDS = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
def _addr():
    import secrets
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(secrets.token_bytes(32), "big") | (1 << 255)
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = alphabet[r] + out
    return out


WALLETS = iter(_addr() for _ in range(100))
_n = itertools.count()


class FakeRPC:
    def __init__(self):
        self.balances, self.transfers = {}, []

    def token_balance_raw(self, owner, mint):
        return self.balances.get(owner, 0)

    def find_transfer(self, sender, recipient, mint, amount_raw, since):
        for s, r, a, sig in self.transfers:
            if (s, r, a) == (sender, recipient, amount_raw):
                return sig
        return None


@pytest.fixture
def rpc(monkeypatch):
    fake = FakeRPC()
    monkeypatch.setattr(appmod, "SOLANA_RPC", fake)
    monkeypatch.setattr(appmod, "TOKEN_MINT", MINT)
    monkeypatch.setattr(appmod, "REWARDS_WALLET", REWARDS)
    appmod.limiter.reset()
    return fake


@pytest.fixture(autouse=True)
def _reset():
    appmod.limiter.reset()


def agent():
    r = client.post("/api/agents/register", json={"name": f"BondBot{next(_n)}", "provider": "Claude"})
    return {"Authorization": "Bearer " + r.json()["api_key"]}


def reply_n(h, n):
    t = client.post("/api/research", headers=h, json={"title": "Bond test research question", "body": "A careful research question with methods and limitations to evaluate.", "category": "Genomics", "sources": []})
    assert t.status_code == 201
    codes = [client.post(f"/api/research/{t.json()['id']}/replies", headers=h, json={"body": "Discussion reply with a source.", "kind": "discussion"}).status_code for _ in range(n)]
    return codes


def verify(h, fake, wallet, balance_tokens):
    assert client.put("/api/me/wallet", headers=h, json={"wallet": wallet}).status_code == 200
    st = client.post("/api/me/bond/verify/start", headers=h).json()
    assert st["send_to"] == REWARDS and 1 < float(st["amount"]) < 2
    assert client.post("/api/me/bond/verify/check", headers=h).json()["verified"] is False
    fake.balances[wallet] = balance_tokens * 10 ** appmod.TOKEN_DECIMALS
    fake.transfers.append((wallet, REWARDS, st["amount_raw"], f"sig{next(_n)}"))
    res = client.post("/api/me/bond/verify/check", headers=h).json()
    assert res["verified"] is True
    return res


def test_free_tier_limit_without_rpc():
    h = agent()
    codes = reply_n(h, 10)  # 1 thread + 10 replies = 11 contributions
    assert codes[:9] == [201] * 9 and codes[9] == 429


def test_verification_unavailable_without_rpc():
    h = agent()
    client.put("/api/me/wallet", headers=h, json={"wallet": "Sysvar1111111111111111111111111111111111111"})
    assert client.post("/api/me/bond/verify/start", headers=h).status_code == 503


def test_verify_and_tier_raises_limits(rpc):
    h = agent()
    res = verify(h, rpc, next(WALLETS), 260_000)
    assert res["tier"]["key"] == "silver"
    d = client.get("/api/me/dashboard", headers=h).json()["bond"]
    assert d["verified"] and d["tier"]["contributions"] == 50 and d["next_tier"]["key"] == "gold"
    assert all(c == 201 for c in reply_n(h, 15))


def test_lowest_balance_counts(rpc):
    h = agent()
    w = next(WALLETS)
    verify(h, rpc, w, 600_000)
    rpc.balances[w] = 50_000 * 10 ** appmod.TOKEN_DECIMALS   # sold after verifying
    assert client.post("/api/governor/bond/snapshot", headers=ADMIN).json()["wallets"] >= 1
    d = client.get("/api/me/dashboard", headers=h).json()["bond"]
    assert d["tier"]["key"] == "free" and d["balance"] == "50000"


def test_wallet_change_resets_verification(rpc):
    h = agent()
    verify(h, rpc, next(WALLETS), 120_000)
    client.put("/api/me/wallet", headers=h, json={"wallet": next(WALLETS)})
    d = client.get("/api/me/dashboard", headers=h).json()["bond"]
    assert d["verified"] is False and d["tier"]["key"] == "free"


def test_reused_signature_rejected(rpc):
    h1, h2 = agent(), agent()
    w1, w2 = next(WALLETS), next(WALLETS)
    verify(h1, rpc, w1, 100_000)
    client.put("/api/me/wallet", headers=h2, json={"wallet": w2})
    st = client.post("/api/me/bond/verify/start", headers=h2).json()
    used_sig = [t for t in rpc.transfers if t[0] == w1][0][3]
    rpc.transfers.append((w2, REWARDS, st["amount_raw"], used_sig))
    assert client.post("/api/me/bond/verify/check", headers=h2).status_code == 409


def test_blocked_addresses(rpc):
    h = agent()
    assert client.put("/api/me/wallet", headers=h, json={"wallet": REWARDS}).status_code == 422


def test_free_pool_cap(rpc):
    shares = appmod.pool_shares({1: 100, 2: 100, 3: 100, 4: 900}, free_ids={1, 2, 3})
    assert sum(shares[k] for k in (1, 2, 3)) <= 1000
    assert shares[4] == 2000  # bonded agent still capped at 20%


def test_no_free_cap_before_bonds_exist():
    shares = appmod.pool_shares({1: 100, 2: 100, 3: 100, 4: 100, 5: 100}, free_ids={1, 2, 3, 4, 5})
    assert sum(shares.values()) >= 9990


def test_rpc_secret_never_exposed(monkeypatch):
    monkeypatch.setattr(appmod, "SOLANA_RPC_URL", "https://rpc.example/?api-key=SECRET123")
    for path in ("/api/health", "/api/bond", "/api/rewards", "/api/limits"):
        assert "SECRET123" not in client.get(path).text


def test_find_transfer_parses_token_balances():
    rpc = bondlib.SolanaRPC("https://example.invalid")
    tx = {"meta": {"err": None,
                   "preTokenBalances": [{"mint": MINT, "owner": "S", "uiTokenAmount": {"amount": "5000000"}},
                                        {"mint": MINT, "owner": REWARDS, "uiTokenAmount": {"amount": "0"}}],
                   "postTokenBalances": [{"mint": MINT, "owner": "S", "uiTokenAmount": {"amount": "3957300"}},
                                         {"mint": MINT, "owner": REWARDS, "uiTokenAmount": {"amount": "1042700"}}]}}
    rpc.call = lambda m, p: [{"signature": "abc", "err": None, "blockTime": 2_000_000_000}] if m == "getSignaturesForAddress" else tx
    assert rpc.find_transfer("S", REWARDS, MINT, 1_042_700, 1_000_000_000) == "abc"
    assert rpc.find_transfer("S", REWARDS, MINT, 1_042_701, 1_000_000_000) is None


def test_tier_parsing():
    tiers = bondlib.parse_tiers("gold:Gold:500000:100:200,bronze:Bronze:100000:25:60,bad")
    assert [t.key for t in tiers] == ["bronze", "gold"]
    free = bondlib.Tier("free", "Free", 0, 10, 20)
    from decimal import Decimal
    assert bondlib.tier_for(Decimal(99_999), tiers, free).key == "free"
    assert bondlib.tier_for(Decimal(100_000), tiers, free).key == "bronze"

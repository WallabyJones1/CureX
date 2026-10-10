"""CureX Research Bond: hold-to-qualify tiers.

An agent links a Solana wallet, proves it owns it with one tiny unique transfer
to the public rewards wallet, and its tier is set by how many $CUREX that wallet
holds. Balances are read from public chain data at random times.

This module is READ-ONLY: it never holds keys, never signs, never moves tokens.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from decimal import Decimal
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Tier:
    key: str
    name: str
    hold: int            # whole tokens required
    contributions: int   # contributions per UTC day
    points: int          # automatic points per UTC day

    def public(self) -> dict:
        return asdict(self)


def parse_tiers(spec: str) -> list[Tier]:
    """'bronze:Bronze:100000:25:60,silver:Silver:250000:50:120' -> tiers sorted by hold."""
    tiers = []
    for part in (spec or "").split(","):
        bits = [b.strip() for b in part.split(":")]
        if len(bits) != 5:
            continue
        key, name, hold, contrib, pts = bits
        try:
            tier = Tier(key.lower()[:16], name[:24], int(hold), int(contrib), int(pts))
        except ValueError:
            continue
        if tier.hold > 0 and tier.contributions > 0 and tier.points > 0:
            tiers.append(tier)
    return sorted(tiers, key=lambda t: t.hold)


def tier_for(balance_tokens: Decimal, tiers: list[Tier], free: Tier) -> Tier:
    best = free
    for t in tiers:
        if balance_tokens >= t.hold:
            best = t
    return best


def next_tier(current: Tier, tiers: list[Tier]) -> Tier | None:
    for t in tiers:
        if t.hold > current.hold:
            return t
    return None


def challenge_amount_raw(decimals: int, taken: set[int]) -> int:
    """A unique amount between 1.0001 and 1.9999 tokens, in raw units."""
    unit = 10 ** decimals
    step = 10 ** max(decimals - 4, 0) if decimals >= 4 else 1
    for _ in range(50):
        raw = unit + (secrets.randbelow(9999) + 1) * step
        if raw not in taken:
            return raw
    raise RuntimeError("Could not allocate a unique verification amount")


class RPCError(RuntimeError):
    pass


class SolanaRPC:
    """Minimal JSON-RPC client for public, read-only Solana queries."""

    def __init__(self, url: str, timeout: float = 10.0):
        if not url.startswith("https://"):
            raise ValueError("Solana RPC URL must use https")
        self.url = url
        self.timeout = timeout

    def call(self, method: str, params: list):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        req = Request(self.url, data=body, method="POST",
                      headers={"Content-Type": "application/json", "User-Agent": "CureX-Bond/1.0"})
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read(2_000_000).decode("utf-8"))
        except Exception as exc:  # network, HTTP or JSON errors; never echo the URL (it may hold an API key)
            raise RPCError(f"Solana RPC request failed ({type(exc).__name__})") from None
        if not isinstance(payload, dict) or payload.get("error"):
            raise RPCError("Solana RPC returned an error")
        return payload.get("result")

    def token_balance_raw(self, owner: str, mint: str) -> int:
        result = self.call("getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}])
        total = 0
        for acct in (result or {}).get("value", []) or []:
            try:
                amount = acct["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]
                total += int(amount)
            except (KeyError, TypeError, ValueError):
                continue
        return total

    def find_transfer(self, sender: str, recipient_owner: str, mint: str, amount_raw: int, since_unix: int) -> str | None:
        """Return the signature of a successful transaction, signed after `since_unix`, in which
        `sender` sent exactly `amount_raw` of `mint` to accounts owned by `recipient_owner`."""
        sigs = self.call("getSignaturesForAddress", [sender, {"limit": 25, "commitment": "confirmed"}]) or []
        for s in sigs:
            if not isinstance(s, dict) or s.get("err") is not None:
                continue
            block_time = s.get("blockTime")
            if block_time is not None and block_time < since_unix:
                break  # newest first; everything after is older
            tx = self.call("getTransaction", [s.get("signature"), {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0, "commitment": "confirmed"}])
            if not tx or (tx.get("meta") or {}).get("err") is not None:
                continue
            meta = tx["meta"]
            delta: dict[str, int] = {}
            for sign, key in ((-1, "preTokenBalances"), (1, "postTokenBalances")):
                for b in meta.get(key) or []:
                    if b.get("mint") != mint or not b.get("owner"):
                        continue
                    try:
                        amt = int(b["uiTokenAmount"]["amount"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    delta[b["owner"]] = delta.get(b["owner"], 0) + sign * amt
            if delta.get(recipient_owner) == amount_raw and delta.get(sender, 0) <= -amount_raw:
                return s.get("signature")
        return None

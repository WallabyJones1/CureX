"""CureX Governor v2 — conservative, explainable community triage.

This is NOT a medical inference model. It never approves scientific findings,
makes medical recommendations, handles wallets or distributes rewards.
Human operator review is necessary before flagged content is restored.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

MEDICAL_HYPE = re.compile(r'\b(?:guaranteed|proven|miracle)\s+(?:cure|treatment|therapy)|100\s*%\s*(?:effective|cure)|\bcures?\s+(?:all\s+)?cancer\b', re.I)
FINANCIAL_HYPE = re.compile(r'\b(?:guaranteed\s+returns?|risk[ -]?free\s+profit|buy\s+now|send\s+(?:sol|usdc|tokens?)|to\s+the\s+moon|100x|1000x|pump\s+it|presale|whitelist\s+spots?|free\s+airdrop|claim\s+your\s+airdrop|dm\s+me)\b', re.I)
SECRETS = re.compile(r'\b(?:private\s+key|seed\s+phrase|secret\s+(?:key|phrase)|recovery\s+phrase|mnemonic|password|api\s+key)\s*[:=]|\bcx_[A-Za-z0-9_-]{30,}', re.I)
# 12/24 lowercase words in a row is the shape of a wallet seed phrase.
SEED_SHAPE = re.compile(r'\b(?:[a-z]{3,8}\s+){11}[a-z]{3,8}\b')
SOLANA_KEY = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')
SOLANA_SECRET = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{86,90}\b|\[\s*(?:\d{1,3}\s*,\s*){63}\d{1,3}\s*\]')
DATA_PRIVACY = re.compile(r'\b(?:patient\s+(?:name|email|phone|address|dob)|medical\s+record\s+number|mrn|date\s+of\s+birth)\s*[:=]', re.I)
SPAM_LINKS = re.compile(r'https?://', re.I)
WALLET_SCAM = re.compile(r'\b(?:connect\s+your\s+wallet|verify\s+your\s+wallet|validate\s+your\s+wallet|wallet\s+sync)\b', re.I)


@dataclass(frozen=True)
class Assessment:
    flags: tuple[str, ...]
    route: str

    @property
    def quarantine(self) -> bool:
        return bool(self.flags)


def assess(text: str, source_count: int = 0, *, kind: str = 'thread') -> Assessment:
    """Deterministic triage; flags are suggestions, not factual judgements."""
    flags: list[str] = []
    if MEDICAL_HYPE.search(text): flags.append('Unqualified treatment/cure claim')
    if FINANCIAL_HYPE.search(text): flags.append('Potential promotional or financial manipulation')
    if SECRETS.search(text) or SOLANA_SECRET.search(text) or SEED_SHAPE.search(text):
        flags.append('Potential secret credential in content')
    if WALLET_SCAM.search(text): flags.append('Possible wallet-drainer / phishing language')
    # Research posts should not carry wallet or contract addresses (token shilling, scam addresses).
    # URLs are excluded; hex hashes/accessions are excluded by requiring mixed case + digits.
    stripped = re.sub(r'https?://\S+', ' ', text)
    if any(re.search(r'[A-Z]', m) and re.search(r'[a-z]', m) and re.search(r'\d', m) for m in SOLANA_KEY.findall(stripped)):
        flags.append('Wallet or contract address in research content')
    if DATA_PRIVACY.search(text): flags.append('Possible identifiable medical information')
    if len(SPAM_LINKS.findall(text)) >= 8: flags.append('Possible link spam')
    if kind == 'thread' and source_count == 0 and len(text) > 450:
        flags.append('Long research post without listed supporting sources')
    return Assessment(flags=tuple(flags), route='human-review' if flags else 'public-unreviewed')


def audit_note(action: str, kind: str, target_id: int) -> str:
    return f'{action}:{kind}:{target_id}'

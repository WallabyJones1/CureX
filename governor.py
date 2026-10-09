"""CureX Governor v1 — conservative, explainable community triage.

This is NOT a medical inference model. It never approves scientific findings,
makes medical recommendations, handles wallets or distributes rewards.
Human operator review is necessary before flagged content is restored.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

MEDICAL_HYPE = re.compile(r'\b(?:guaranteed|proven|miracle)\s+(?:cure|treatment|therapy)|100\s*%\s*(?:effective|cure)',re.I)
FINANCIAL_HYPE = re.compile(r'\b(?:guaranteed\s+returns|risk[ -]?free\s+profit|buy\s+now|send\s+sol)\b',re.I)
SECRETS = re.compile(r'\b(?:private\s+key|seed\s+phrase|password|api\s+key)\s*[:=]',re.I)
DATA_PRIVACY = re.compile(r'\b(?:patient\s+email|patient\s+phone|medical\s+record\s+number)\s*[:=]',re.I)
SPAM_LINKS = re.compile(r'https?://',re.I)

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
    if SECRETS.search(text): flags.append('Potential secret credential in content')
    if DATA_PRIVACY.search(text): flags.append('Possible identifiable medical information')
    if len(SPAM_LINKS.findall(text)) >= 8: flags.append('Possible link spam')
    if kind == 'thread' and source_count == 0 and len(text) > 450:
        flags.append('Long research post without listed supporting sources')
    return Assessment(flags=tuple(flags), route='human-review' if flags else 'public-unreviewed')


def audit_note(action: str, kind: str, target_id: int) -> str:
    return f'{action}:{kind}:{target_id}'

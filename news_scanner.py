"""Bounded, citation-first Europe PMC research-news scanner for CureX Governor.

No language model; no external URLs supplied by users; no article bodies copied.
The scanner produces questions for discussion, never clinical recommendations.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import date
import json
import re

EUROPE_PMC_API = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'
TOPICS = {
    'Immunotherapy': ('(lung cancer OR NSCLC) AND (immunotherapy OR PD-1 OR resistance)', 'Oncology'),
    'AI Cancer Research': ('(cancer OR oncology) AND (artificial intelligence OR machine learning OR computational pathology)', 'AI & Methods'),
    'Genomics': ('(cancer OR tumour) AND (single-cell OR genomics OR ctDNA)', 'Genomics'),
}


def _read_json(url: str) -> dict:
    request = Request(url, headers={'User-Agent': 'CureX-Research-Governor/0.1 (https://curex.world)', 'Accept': 'application/json'})
    with urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise RuntimeError('Research source unavailable')
        payload = response.read(450_000)
    return json.loads(payload.decode('utf-8'))


def scan_articles(fetch=_read_json, clock=None, days=21, page_size=15) -> list[dict]:
    """Fetch recent, dated, identifiable publications. Failing feeds cause an error, not fabricated posts."""
    clock = clock or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError('timezone-aware clock required')
    start = (clock.date() - timedelta(days=days)).isoformat()
    end = clock.date().isoformat()
    output: list[dict] = []
    for topic, (terms, category) in TOPICS.items():
        query = f'({terms}) AND FIRST_PDATE:[{start} TO {end}] sort_date:y'
        url = EUROPE_PMC_API + '?' + urlencode({'query': query, 'format': 'json', 'resultType': 'lite', 'pageSize': max(1, min(page_size, 25))})
        data = fetch(url)
        results = data.get('resultList', {}).get('result', [])
        if not isinstance(results, list):
            raise RuntimeError('Unexpected Europe PMC result')
        for a in results:
            title = re.sub(r'\s+', ' ', str(a.get('title', ''))).strip()[:230]
            published = str(a.get('firstPublicationDate') or a.get('firstIndexDate') or '')[:10]
            if not title or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', published) or not (start <= published <= end):
                continue
            # Never turn preprints into seemingly peer-reviewed announcements.
            if str(a.get('source','')).upper() == 'PPR':
                continue
            # Avoid automatically promoting papers the index marks as retracted.
            if str(a.get('isRetracted', '')).lower() in ('true', 'y', 'yes', '1'):
                continue
            doi = str(a.get('doi') or '').strip()
            pmid = str(a.get('pmid') or '').strip()
            if not (doi.startswith('10.') or pmid.isdecimal()):
                continue
            identity = 'doi:' + doi.lower() if doi.startswith('10.') else 'pmid:' + pmid
            source_url = 'https://doi.org/' + doi if doi.startswith('10.') else 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/'
            output.append({
                'source_id': identity, 'title': title, 'published_at': published,
                'source_url': source_url, 'journal': str(a.get('journalTitle') or 'Europe PMC indexed publication')[:140],
                'category': category, 'topic': topic,
                'doi': doi, 'pmid': pmid,
            })
    unique={x['source_id']:x for x in output}
    return sorted(unique.values(),key=lambda x:(x['published_at'],x['title']),reverse=True)


def discussion_prompt(article: dict) -> str:
    """No paraphrasing of results or unverified AI claims; asks researchers to inspect the source."""
    return (f"**New source for community discussion — not a validated finding**\n\n"
            f"Publication: {article['title']}\n"
            f"Journal / index: {article['journal']} · Published: {article['published_at']}\n"
            f"Primary record: {article['source_url']}\n\n"
            f"**Research questions:** What is the study design and sample size? Which claims are supported by the reported methods and results? "
            f"Are there independent replications, important limitations, or conflicting studies?\n\n"
            f"Automatically indexed by the CureX News Governor. This is a discussion prompt, not an endorsement, "
            f"clinical recommendation, or evidence of a cure. Read the original paper before drawing conclusions.")

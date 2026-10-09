"""API smoke and regression tests. Run with: python -m pytest -q"""
import os
import tempfile
from pathlib import Path

_TEMP = tempfile.TemporaryDirectory(prefix='curex-test-')
os.environ['DATABASE_PATH'] = str(Path(_TEMP.name) / 'db.sqlite3')
os.environ['CUREX_PUBLIC_WRITE_ENABLED'] = 'true'
os.environ['CUREX_OPERATOR_NAME'] = 'CureX Test Operator'
os.environ['CUREX_PRIVACY_CONTACT'] = 'privacy@example.org'
os.environ['CUREX_RATE_SALT'] = 'test-salt'
os.environ['CUREX_RATE_READ'] = '500'
os.environ['CUREX_RATE_WRITE'] = '500'
os.environ['CUREX_RATE_REGISTER'] = '500'
os.environ['CUREX_RATE_MCP'] = '500'

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_site_and_public_endpoints():
    assert client.get('/').status_code == 200
    assert b'CureX Network' in client.get('/').content
    assert client.get('/assets/curex-logo.png').status_code == 200
    assert client.get('/assets/app.js').status_code == 200
    assert client.get('/api/health').json()['payments'] == 'disabled'
    assert len(client.get('/api/research').json()) == 4
    assert len(client.get('/api/bounties').json()) == 3


def register_test_agent():
    response=client.post('/api/agents/register',json={'name':'Test Oncology Reviewer','provider':'Open-source / Local','description':'Independent testing agent'})
    assert response.status_code == 201, response.text
    token=response.json()['api_key']
    assert token.startswith('cx_')
    assert token not in client.get('/api/agents').text
    assert client.get('/api/me').status_code == 401
    assert client.get('/api/me',headers={'Authorization':f'Bearer {token}'}).json()['name']=='Test Oncology Reviewer'
    return token


def test_agent_registration_and_private_key():
    assert register_test_agent().startswith("cx_")


def test_authorized_posts_and_replies():
    token=register_test_agent() if not client.get('/api/agents').json() else None
    if not token:
        # Need a new unique agent if tests run in arbitrary order.
        from uuid import uuid4
        token=client.post('/api/agents/register',json={'name':'Test Agent '+uuid4().hex[:6],'provider':'Local'}).json()['api_key']
    h={'Authorization':f'Bearer {token}'}
    post={'title':'Assessing immune escape signatures in NSCLC','body':'Propose reproducible cross-cohort comparison of interferon signalling, with limitations and external replication.', 'category':'Oncology','sources':['https://www.ncbi.nlm.nih.gov/geo/']}
    assert client.post('/api/research',json=post).status_code==401
    result=client.post('/api/research',json=post,headers=h)
    assert result.status_code==201,result.text
    tid=result.json()['id']
    assert client.get(f'/api/research/{tid}').json()['thread']['title']==post['title']
    reply=client.post(f'/api/research/{tid}/replies',headers=h,json={'kind':'review','body':'The effect sizes and endpoint harmonisation still need review.'})
    assert reply.status_code==201
    assert len(client.get(f'/api/research/{tid}').json()['replies'])==1
    assert client.post('/api/townhall',headers=h,json={'body':'I will test the evidence review protocol.'}).status_code==201
    assert client.post('/api/research',headers=h,json={**post,'sources':['http://example.com']}).status_code==422
    assert any(p['id']==tid for p in client.get('/api/research?q=immune%20escape&category=Oncology').json())


def test_governor_flags_unsubstantiated_claims():
    from uuid import uuid4
    token=client.post('/api/agents/register',json={'name':'Review Bot '+uuid4().hex[:6],'provider':'Local'}).json()['api_key']
    result=client.post('/api/research',headers={'Authorization':f'Bearer {token}'},json={'title':'A guaranteed cure for all cancers','body':'A guaranteed cure is proven effective at 100% but this post has no credible data or methodology and requires review.','category':'General Research'})
    assert result.status_code==201
    assert result.json()['status']=='needs-review'
    assert client.get('/api/governor').json()['flagged_count'] >= 1
    assert all(x['id'] != result.json()['id'] for x in client.get('/api/research').json())
    assert client.get(f"/api/research/{result.json()['id']}").status_code == 404


def test_mcp_readonly_tool_protocol():
    init=client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
    assert init.json()['result']['serverInfo']['name']=='CureX Research Network'
    tools=client.post('/mcp',json={'jsonrpc':'2.0','id':2,'method':'tools/list'}).json()['result']['tools']
    assert len(tools)==5
    call=client.post('/mcp',json={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_network_stats','arguments':{}}}).json()
    assert call['result']['content'][0]['type']=='text'
    assert client.post('/mcp',json={'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'execute_payment','arguments':{}}}).json()['error']['code']==-32602


def test_policy_pages_and_security_headers():
    for url in ('/privacy', '/terms', '/community-rules'):
        r=client.get(url)
        assert r.status_code == 200
        assert 'CureX' in r.text
        assert r.headers['X-Frame-Options']=='DENY'
        assert "default-src 'self'" in r.headers['Content-Security-Policy']
    assert client.get('/api/limits').json()['public_writes'] is True
    assert client.get('/robots.txt').status_code == 200
    assert 'CureX' in client.get('/.well-known/security.txt').text or 'privacy@' in client.get('/.well-known/security.txt').text

def test_readonly_flag_and_explicit_rate_limiting(monkeypatch):
    import app as module
    monkeypatch.setattr(module, 'PUBLIC_WRITE_ENABLED', False)
    response=client.post('/api/agents/register',json={'name':'Blocked Tester','provider':'Local'})
    assert response.status_code==503
    assert client.get('/api/health').json()['public_writes'] is False
    monkeypatch.setattr(module, 'PUBLIC_WRITE_ENABLED', True)
    # 1 request/minute on a unique class of endpoint; ensure the limiter works.
    monkeypatch.setattr(module, 'RATE_MCP', 1)
    first=client.post('/mcp',json={'jsonrpc':'2.0','id':900,'method':'ping'})
    second=client.post('/mcp',json={'jsonrpc':'2.0','id':901,'method':'ping'})
    assert second.status_code==429
    assert second.headers['Retry-After']
    monkeypatch.setattr(module, 'RATE_MCP', 500)

def test_request_size_and_mcp_bad_json():
    oversized=client.post('/mcp',content=b'x'*(33*1024),headers={'Content-Type':'application/json'})
    assert oversized.status_code==413
    malformed=client.post('/mcp',content='{bad json',headers={'Content-Type':'application/json'})
    assert malformed.status_code==400


def test_agent_key_rotation_and_account_removal():
    from uuid import uuid4
    old=client.post('/api/agents/register',json={'name':'Rotate '+uuid4().hex[:10], 'provider':'Local'})
    assert old.status_code == 201
    token=old.json()['api_key']
    rotation=client.post('/api/me/rotate-key',headers={'Authorization':f'Bearer {token}'})
    assert rotation.status_code == 200
    fresh=rotation.json()['api_key']
    assert fresh != token
    assert client.get('/api/me',headers={'Authorization':f'Bearer {token}'}).status_code==401
    assert client.get('/api/me',headers={'Authorization':f'Bearer {fresh}'}).status_code==200
    removal=client.delete('/api/me',headers={'Authorization':f'Bearer {fresh}'})
    assert removal.status_code==200
    assert removal.json()['deleted'] is True
    assert client.get('/api/me',headers={'Authorization':f'Bearer {fresh}'}).status_code==401

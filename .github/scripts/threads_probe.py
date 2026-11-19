# Testlauf Threads-Statistik (nur lesen) -> fb/threads-test.json
import os, json, urllib.request, urllib.parse, datetime as dt, time
G='https://graph.threads.net/v1.0/'; tok=os.environ['THREADS_TOKEN']
def get(path, **p):
    p['access_token']=tok
    try:
        with urllib.request.urlopen(G+path+'?'+urllib.parse.urlencode(p),timeout=40) as r: return {'ok':1,'d':json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        try: m=json.loads(e.read().decode()).get('error',{}).get('message','')
        except Exception: m=''
        return {'ok':0,'f':m[:200]}
out={}
me=get('me',fields='id,username,threads_biography')
out['profil']=me['d'] if me['ok'] else me['f']
since=int(time.time())-7*86400; until=int(time.time())
for m in ['views','likes','replies','reposts','quotes','clicks','followers_count','follower_demographics']:
    p={'metric':m}
    if m not in ('followers_count','follower_demographics'): p.update(since=since,until=until)
    if m=='follower_demographics': p['breakdown']='country'
    r=get('me/threads_insights',**p)
    out['profil:'+m]=(json.dumps(r['d'].get('data',[]),ensure_ascii=False)[:300] if r['d'].get('data') else 'leer') if r['ok'] else 'FEHLER: '+r['f']
L=get('me/threads',fields='id,timestamp,text,media_type,permalink',limit=5)
out['beitraege']=[(x.get('timestamp'),x.get('media_type'),(x.get('text') or '')[:40]) for x in L['d'].get('data',[])] if L['ok'] else L['f']
if L['ok'] and L['d'].get('data'):
    r=get(L['d']['data'][0]['id']+'/insights',metric='views,likes,replies,reposts,quotes,shares')
    out['beitrag:insights']=[{x['name']:(x.get('values') or [{}])[0].get('value', (x.get('total_value') or {}).get('value'))} for x in r['d'].get('data',[])] if r['ok'] else 'FEHLER: '+r['f']
s=json.dumps({'stand':dt.datetime.now().isoformat(timespec='minutes'),'tests':out},ensure_ascii=False,indent=1)
assert tok not in s
open('fb/threads-test.json','w').write(s); print(s)

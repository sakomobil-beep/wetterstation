# Testlauf: welche Kennzahlen liefert Meta? (nur lesen) -> fb/insights-test.json
import os, json, urllib.request, urllib.parse, datetime as dt
G='https://graph.facebook.com/v21.0/'; tok=os.environ['FB_PAGE_TOKEN']; tok0=tok; pid=os.environ['FB_PAGE_ID']
def get(path, **p):
    p['access_token']=tok
    try:
        with urllib.request.urlopen(G+path+'?'+urllib.parse.urlencode(p),timeout=40) as r: return {'ok':1,'d':json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        try: m=json.loads(e.read().decode()).get('error',{}).get('message','')
        except Exception: m=''
        return {'ok':0,'f':m[:160]}
t=get(pid,fields='access_token'); tok=t['d']['access_token']
out={}
def kurz(r):
    if not r['ok']: return 'FEHLER: '+r['f']
    D=r['d'].get('data',[])
    if not D: return 'leer'
    return [{x['name']+('/'+x.get('period','') if x.get('period') else ''):(x.get('values') or [{}])[-1].get('value', x.get('total_value'))} for x in D][:3]
h=dt.date.today()
r=get(pid+'/insights',metric='page_media_view',period='day',breakdown='is_from_followers',since=str(h-dt.timedelta(days=2)),until=str(h))
out['folgerbreakdown']=r['d'] if r['ok'] else r['f']
P=get(pid+'/posts',fields='id,created_time,message',limit=12)
n=0
for p in P['d'].get('data',[]):
    msg=(p.get('message') or '')[:30]
    r=get(p['id']+'/insights',metric='post_video_avg_time_watched,post_video_view_time,post_video_complete_views_30s,post_video_views,post_activity_by_action_type,post_clicks_by_type,post_reactions_by_type_total')
    out['beitrag '+p['created_time'][:16]+' '+msg]=kurz(r) if not r['ok'] else [{x['name']:(x.get('values') or [{}])[0].get('value')} for x in r['d'].get('data',[])]
    g=get(p['id']+'/insights',metric='post_video_retention_graph')
    if g['ok'] and g['d'].get('data'):
        v=g['d']['data'][0].get('values',[{}])[0].get('value');out['retention '+msg]=str(v)[:300];n+=1
    if n>=2: break
pv=get(pid+'/video_reels',fields='id,created_time',limit=2)
out['reels']=pv['d'].get('data') if pv['ok'] else pv['f']
if pv['ok'] and pv['d'].get('data'):
    rid=pv['d']['data'][0]['id'];r=get(rid+'/video_insights')
    out['reel-insights']=[{x['name']:(x.get('values') or [{}])[0].get('value')} for x in r['d'].get('data',[])] if r['ok'] else r['f']
s=json.dumps({'stand':dt.datetime.now().isoformat(timespec='minutes'),'tests':out},ensure_ascii=False,indent=1)
assert tok not in s and tok0 not in s
open('fb/insights-test.json','w').write(s); print(s)

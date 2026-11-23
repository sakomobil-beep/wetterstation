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
def T(name,fn):
    try: out[name]=fn()
    except Exception as e: out[name]='PYFEHLER: '+repr(e)[:200]
T('folgerbreakdown',lambda: (lambda r: r['d'].get('data') if r['ok'] else r['f'])(get(pid+'/insights',metric='page_media_view',period='day',breakdown='is_from_followers',since=str(h-dt.timedelta(days=2)),until=str(h))))
P=get(pid+'/posts',fields='id,created_time,message',limit=12)
PL=P['d'].get('data',[]) if P['ok'] else []
out['posts_ok']=P['ok'] and len(PL)
def postt():
    res={}
    for p in PL[:4]:
        k=p['created_time'][:16]+' '+(p.get('message') or '')[:25]; res[k]={}
        for m in ['post_video_avg_time_watched','post_video_view_time','post_video_complete_views_30s','post_video_views','post_activity_by_action_type','post_clicks_by_type','post_reactions_by_type_total','post_video_retention_graph','post_video_length']:
            r=get(p['id']+'/insights',metric=m)
            res[k][m]=(str((r['d'].get('data') or [{}])[0].get('values',[{}])[0].get('value'))[:160] if r['d'].get('data') else 'leer') if r['ok'] else 'F:'+r['f'][:60]
    return res
T('beitraege',postt)
def reels():
    pv=get(pid+'/video_reels',fields='id,created_time',limit=2)
    if not pv['ok']: return pv['f']
    D=pv['d'].get('data',[])
    if not D: return 'keine'
    r=get(D[0]['id']+'/video_insights')
    return [{x['name']:str((x.get('values') or [{}])[0].get('value'))[:120]} for x in r['d'].get('data',[])] if r['ok'] else r['f']
T('reels',reels)
s=json.dumps({'stand':dt.datetime.now().isoformat(timespec='minutes')+' L6','tests':out},ensure_ascii=False,indent=1)
assert tok not in s and tok0 not in s
open('fb/insights-test.json','w').write(s); print(s)

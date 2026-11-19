# Facebook- und Instagram-Statistik abholen (nur lesen) -> fb/insights.json (19.11.2026)
import os, json, re, urllib.request, urllib.parse, datetime as dt
G='https://graph.facebook.com/v21.0/'
tok=os.environ['FB_PAGE_TOKEN']; pid=os.environ['FB_PAGE_ID']; tok0=tok
def get(path, **p):
    p['access_token']=tok
    try:
        with urllib.request.urlopen(G+path+'?'+urllib.parse.urlencode(p),timeout=40) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: m=json.loads(e.read().decode()).get('error',{}).get('message','')
        except Exception: m=''
        print('Hinweis', path, e.code, m[:200]); return None
pt=get(pid,fields='access_token')
if pt and pt.get('access_token'): tok=pt['access_token']
P='fb/insights.json'
try: alt=json.load(open(P))
except Exception: alt={}
heute=dt.date.today(); out={'stand':dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes'),'fb':{},'ig':{}}
# Facebook Seite
s=get(pid,fields='name,followers_count,instagram_business_account') or {}
out['fb']['follower']=s.get('followers_count')
tage=alt.get('fb',{}).get('tage',{})
M=['page_follows','page_daily_follows_unique','page_media_view','page_total_media_view_unique','page_video_views','page_post_engagements']
for m in M:
    r=get(pid+'/insights',metric=m,period='day',since=str(heute-dt.timedelta(days=90)),until=str(heute))
    for x in (r or {}).get('data',[]):
        for v in x.get('values',[]):
            d=(dt.datetime.fromisoformat(v['end_time'].replace('+0000','+00:00'))-dt.timedelta(days=1)).date().isoformat()
            val=v.get('value'); val=sum(val.values()) if isinstance(val,dict) else val
            tage.setdefault(d,{})[m.replace('page_','')]=val
out['fb']['tage']=dict(sorted(tage.items()))  # dauerhaft, keine Begrenzung (19.11.2026)
def art(t,h):
    t=(t or '').strip(); k=t[:60].lower()
    if 'wetterwissen' in k: return 'wissen'
    if 'wochenausblick' in k: return 'woche'
    if 'rückblick' in k: return 'rueckblick'
    if 'guten abend' in k: return 'abend'
    if 'guten morgen' in k or 'euer odenwald-wetter' in k: return 'morgen'
    if 'nachmittag im odenwald' in k or 'mittag' in k: return 'mittag'
    if re.search(r'warnung|unwetter|dwd',k): return 'warnung'
    if h<11: return 'morgen'
    if h>=18: return 'abend'
    return 'sonst'
posts=[]
r=get(pid+'/posts',fields='id,created_time,message,full_picture,permalink_url',limit=60,since=str(heute-dt.timedelta(days=35)))
for p in (r or {}).get('data',[]):
    i=get(p['id']+'/insights',metric='post_media_view,post_total_media_view_unique,post_reactions_by_type_total,post_clicks') or {}
    w={}
    for x in i.get('data',[]):
        if x.get('values') and x['name'] not in w: w[x['name']]=x['values'][0]['value']
    ct=dt.datetime.fromisoformat(p['created_time'].replace('+0000','+00:00')).astimezone(dt.timezone(dt.timedelta(hours=1)))
    rk=w.get('post_reactions_by_type_total') or {}
    posts.append({'id':p['id'],'p':'fb','zeit':ct.isoformat(timespec='minutes'),'text':(p.get('message') or '')[:120],'bild':p.get('full_picture'),'link':p.get('permalink_url'),
      'art':art(p.get('message'),ct.hour),'views':w.get('post_media_view'),'personen':w.get('post_total_media_view_unique'),'likes':sum(rk.values()) if isinstance(rk,dict) else rk,'klicks':w.get('post_clicks')})
# Instagram
ig=(s.get('instagram_business_account') or {}).get('id')
if ig:
    a=get(ig,fields='username,followers_count,media_count') or {}
    out['ig'].update({'name':a.get('username'),'follower':a.get('followers_count'),'beitraege':a.get('media_count')})
    it=alt.get('ig',{}).get('tage',{})
    for m in ['reach','follower_count']:
        r=get(ig+'/insights',metric=m,period='day',since=str(heute-dt.timedelta(days=29)),until=str(heute))
        for x in (r or {}).get('data',[]):
            for v in x.get('values',[]):
                d=(dt.datetime.fromisoformat(v['end_time'].replace('+0000','+00:00'))-dt.timedelta(days=1)).date().isoformat()
                it.setdefault(d,{})[m]=v.get('value')
    out['ig']['tage']=dict(sorted(it.items()))
    on=get(ig+'/insights',metric='online_followers',period='lifetime')
    try: out['ig']['online']=on['data'][0]['values'][-1]['value']
    except Exception: pass
    r=get(ig+'/media',fields='id,timestamp,caption,media_type,media_product_type,thumbnail_url,media_url,permalink',limit=40) or {}
    for p in r.get('data',[]):
        ct=dt.datetime.fromisoformat(p['timestamp'].replace('+0000','+00:00')).astimezone(dt.timezone(dt.timedelta(hours=1)))
        if ct.date()<heute-dt.timedelta(days=35): continue
        i=get(p['id']+'/insights',metric='views,reach,likes,comments,saved') or {}
        w={x['name']:(x.get('values') or [{}])[0].get('value', x.get('total_value',{}).get('value')) for x in i.get('data',[])}
        posts.append({'id':p['id'],'p':'ig','zeit':ct.isoformat(timespec='minutes'),'text':(p.get('caption') or '')[:120],'bild':p.get('thumbnail_url') or p.get('media_url'),'link':p.get('permalink'),
          'art':art(p.get('caption'),ct.hour),'views':w.get('views'),'personen':w.get('reach'),'likes':w.get('likes'),'klicks':w.get('comments')})
# Beitrags-Archiv: jeder Beitrag bleibt für immer, Zahlen werden fortgeschrieben (19.11.2026)
arch={(b.get('id') or b['p']+b['zeit']):b for b in alt.get('beitraege',[])}
for b in posts:
    k=b.get('id') or b['p']+b['zeit']; a=arch.get(k,{})
    for f in ('views','personen','likes','klicks'):
        if b.get(f) is None and a.get(f) is not None: b[f]=a[f]
    b['stand']=heute.isoformat(); arch[k]=b
out['beitraege']=sorted(arch.values(),key=lambda x:x['zeit'],reverse=True)
t=json.dumps(out,ensure_ascii=False)
assert tok not in t and tok0 not in t
open(P,'w').write(t)
print('Facebook-Follower',out['fb'].get('follower'),'· Tage',len(out['fb']['tage']),'· Beiträge',len(posts),'· Instagram',out['ig'].get('follower'))

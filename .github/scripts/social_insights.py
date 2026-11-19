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
M=['page_follows','page_daily_follows_unique','page_daily_unfollows_unique','page_media_view','page_total_media_view_unique','page_video_views','page_post_engagements','page_video_view_time','page_video_complete_views_30s','page_actions_post_reactions_total']
for m in M:
    r=get(pid+'/insights',metric=m,period='day',since=str(heute-dt.timedelta(days=90)),until=str(heute))
    for x in (r or {}).get('data',[]):
        for v in x.get('values',[]):
            d=(dt.datetime.fromisoformat(v['end_time'].replace('+0000','+00:00'))-dt.timedelta(days=1)).date().isoformat()
            val=v.get('value')
            if isinstance(val,dict) and m!='page_actions_post_reactions_total': val=sum(val.values())
            tage.setdefault(d,{})[m.replace('page_','')]=val
r=get(pid+'/insights',metric='page_media_view',period='day',breakdown='is_from_followers',since=str(heute-dt.timedelta(days=90)),until=str(heute))
for x in (r or {}).get('data',[]):
    for v in x.get('values',[]):
        d=(dt.datetime.fromisoformat(v['end_time'].replace('+0000','+00:00'))-dt.timedelta(days=1)).date().isoformat()
        tage.setdefault(d,{})['views_follower' if str(v.get('is_from_followers'))=='1' else 'views_andere']=v.get('value')
for m,key in [('page_follows_city','orte'),('page_follows_country','laender')]:
    r=get(pid+'/insights',metric=m,period='day')
    try:
        v=r['data'][0]['values'][-1]['value']
        if v: out['fb'][key]=v
    except Exception: pass
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
    i=get(p['id']+'/insights',metric='post_media_view,post_total_media_view_unique,post_reactions_by_type_total,post_clicks,post_clicks_by_type,post_activity_by_action_type,post_video_views,post_video_avg_time_watched,post_video_view_time,post_video_complete_views_30s,post_video_length,post_video_retention_graph') or {}
    w={}
    for x in i.get('data',[]):
        if x.get('values') and x['name'] not in w: w[x['name']]=x['values'][0]['value']
    ct=dt.datetime.fromisoformat(p['created_time'].replace('+0000','+00:00')).astimezone(dt.timezone(dt.timedelta(hours=1)))
    rk=w.get('post_reactions_by_type_total') or {}
    posts.append({'id':p['id'],'p':'fb','zeit':ct.isoformat(timespec='minutes'),'text':(p.get('message') or '')[:120],'bild':p.get('full_picture'),'link':p.get('permalink_url'),
      'art':art(p.get('message'),ct.hour),'views':w.get('post_media_view'),'personen':w.get('post_total_media_view_unique'),'likes':sum(rk.values()) if isinstance(rk,dict) else rk,'klicks':w.get('post_clicks'),
      'reaktionen':rk if isinstance(rk,dict) else None,'klickarten':w.get('post_clicks_by_type') or None,
      'geteilt':(w.get('post_activity_by_action_type') or {}).get('share',0),'kommentare':(w.get('post_activity_by_action_type') or {}).get('comment',0)})
    vl=w.get('post_video_length') or 0
    if vl:
        rg=w.get('post_video_retention_graph') or {}
        posts[-1].update({'video':{'laenge':round(vl/1000,1),'aufrufe':w.get('post_video_views'),'sehdauer':round((w.get('post_video_avg_time_watched') or 0)/1000,1),
          'sehzeit_min':round((w.get('post_video_view_time') or 0)/60000,1),'voll30':w.get('post_video_complete_views_30s'),
          'verlauf':[round(float(rg[k]),3) for k in sorted(rg,key=lambda z:int(z))] if isinstance(rg,dict) else None}})
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
    for back in range(1,8):
        d0=heute-dt.timedelta(days=back)
        r=get(ig+'/insights',metric='views,accounts_engaged,total_interactions,likes,comments,shares,saves,profile_links_taps',period='day',metric_type='total_value',since=str(d0),until=str(d0+dt.timedelta(days=1)))
        for x in (r or {}).get('data',[]):
            it.setdefault(str(d0),{})[x['name']]=(x.get('total_value') or {}).get('value')
    out['ig']['tage']=dict(sorted(it.items()))
    for b in ['city','age','gender']:
        r=get(ig+'/insights',metric='follower_demographics',period='lifetime',metric_type='total_value',breakdown=b)
        try:
            R=r['data'][0]['total_value']['breakdowns'][0]['results']
            if R: out['ig'].setdefault('demografie',{})[b]={x['dimension_values'][0]:x['value'] for x in R}
        except Exception: pass
    on=get(ig+'/insights',metric='online_followers',period='lifetime')
    try: out['ig']['online']=on['data'][0]['values'][-1]['value']
    except Exception: pass
    r=get(ig+'/media',fields='id,timestamp,caption,media_type,media_product_type,thumbnail_url,media_url,permalink',limit=40) or {}
    for p in r.get('data',[]):
        ct=dt.datetime.fromisoformat(p['timestamp'].replace('+0000','+00:00')).astimezone(dt.timezone(dt.timedelta(hours=1)))
        if ct.date()<heute-dt.timedelta(days=35): continue
        i=get(p['id']+'/insights',metric='views,reach,likes,comments,saved,shares'+(',ig_reels_avg_watch_time,ig_reels_video_view_total_time' if p.get('media_product_type')=='REELS' else '')) or {}
        if not i: i=get(p['id']+'/insights',metric='views,reach,likes,comments,saved') or {}
        w={x['name']:(x.get('values') or [{}])[0].get('value', x.get('total_value',{}).get('value')) for x in i.get('data',[])}
        posts.append({'id':p['id'],'p':'ig','zeit':ct.isoformat(timespec='minutes'),'text':(p.get('caption') or '')[:120],'bild':p.get('thumbnail_url') or p.get('media_url'),'link':p.get('permalink'),
          'art':art(p.get('caption'),ct.hour),'views':w.get('views'),'personen':w.get('reach'),'likes':w.get('likes'),'klicks':w.get('comments'),'kommentare':w.get('comments'),'geteilt':w.get('shares'),'gespeichert':w.get('saved')})
        if w.get('ig_reels_avg_watch_time') is not None: posts[-1]['video']={'sehdauer':round(w['ig_reels_avg_watch_time']/1000,1),'sehzeit_min':round((w.get('ig_reels_video_view_total_time') or 0)/60000,1),'aufrufe':w.get('views')}
# Threads (20.11.2026)
TT=os.environ.get('THREADS_TOKEN')
if TT:
    def tget(path, **p):
        p['access_token']=TT
        try:
            with urllib.request.urlopen('https://graph.threads.net/v1.0/'+path+'?'+urllib.parse.urlencode(p),timeout=40) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            print('Threads-Hinweis', path, e.code); return None
    import time
    out['th']={}; tt=alt.get('th',{}).get('tage',{})
    me=tget('me',fields='username') or {}; out['th']['name']=me.get('username')
    fc=tget('me/threads_insights',metric='followers_count') or {}
    try: out['th']['follower']=fc['data'][0]['total_value']['value']; tt.setdefault((heute-dt.timedelta(days=1)).isoformat(),{})['follower']=out['th']['follower']
    except Exception: pass
    for back in range(1,8):
        d0=heute-dt.timedelta(days=back); a0=int(dt.datetime(d0.year,d0.month,d0.day,tzinfo=dt.timezone(dt.timedelta(hours=1))).timestamp())
        r=tget('me/threads_insights',metric='views,likes,replies,reposts,quotes,clicks',since=a0,until=a0+86400) or {}
        for x in r.get('data',[]):
            if x['name']=='views': v=sum(w.get('value',0) for w in x.get('values',[]))
            elif x['name']=='clicks': v=sum(w.get('value',0) for w in x.get('link_total_values',[]))
            else: v=(x.get('total_value') or {}).get('value')
            tt.setdefault(str(d0),{})[x['name']]=v
    out['th']['tage']=dict(sorted(tt.items()))
    L=tget('me/threads',fields='id,timestamp,text,media_type,permalink,media_url,thumbnail_url',limit=60,since=int(time.time())-35*86400) or {}
    for p in L.get('data',[]):
        i=tget(p['id']+'/insights',metric='views,likes,replies,reposts,quotes,shares') or {}
        w={x['name']:((x.get('values') or [{}])[0].get('value') if x.get('values') else (x.get('total_value') or {}).get('value')) for x in i.get('data',[])}
        ct=dt.datetime.fromisoformat(p['timestamp'].replace('+0000','+00:00')).astimezone(dt.timezone(dt.timedelta(hours=1)))
        tx=p.get('text') or ''
        posts.append({'id':p['id'],'p':'th','zeit':ct.isoformat(timespec='minutes'),'text':tx[:120],'bild':p.get('thumbnail_url') or (p.get('media_url') if p.get('media_type')=='IMAGE' else None),'link':p.get('permalink'),
          'art':art(tx,ct.hour) if 'so wird das wetter morgen' not in tx[:60].lower() else 'abend','views':w.get('views'),'likes':w.get('likes'),'klicks':w.get('replies'),'kommentare':w.get('replies'),'geteilt':(w.get('reposts') or 0)+(w.get('shares') or 0),'zitate':w.get('quotes')})
# Beitrags-Archiv: jeder Beitrag bleibt für immer, Zahlen werden fortgeschrieben (19.11.2026)
arch={b['p']+b['zeit']:b for b in alt.get('beitraege',[])}
for b in posts:
    k=b['p']+b['zeit']; a=arch.get(k,{})
    for f in ('views','personen','likes','klicks','geteilt','kommentare','video','reaktionen','klickarten'):
        if b.get(f) is None and a.get(f) is not None: b[f]=a[f]
    b['stand']=heute.isoformat(); arch[k]=b
out['beitraege']=sorted(arch.values(),key=lambda x:x['zeit'],reverse=True)
t=json.dumps(out,ensure_ascii=False)
assert tok not in t and tok0 not in t and (not TT or TT not in t)
open(P,'w').write(t)
print('Facebook-Follower',out['fb'].get('follower'),'· Tage',len(out['fb']['tage']),'· Beiträge',len(posts),'· Instagram',out['ig'].get('follower'))

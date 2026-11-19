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
for m in ['page_daily_unfollows_unique','page_media_view','page_video_view_time','page_video_complete_views_30s','page_video_views_organic','page_actions_post_reactions_total','page_follows_city','page_follows_country']:
    out['seite:'+m]=kurz(get(pid+'/insights',metric=m,period='day',since=str(h-dt.timedelta(days=3)),until=str(h)))
out['seite:page_media_view nach is_from_followers']=kurz(get(pid+'/insights',metric='page_media_view',period='day',breakdown='is_from_followers',since=str(h-dt.timedelta(days=3)),until=str(h)))
vids=get(pid+'/videos',fields='id,created_time,length,title,description',limit=3)
out['videos']=[(v['id'][-4:],v.get('length'),v.get('created_time')) for v in vids.get('d',{}).get('data',[])] if vids['ok'] else vids['f']
if vids['ok'] and vids['d'].get('data'):
    vid=vids['d']['data'][0]['id']
    for m in ['total_video_views','total_video_avg_time_watched','total_video_view_total_time','total_video_complete_views','total_video_30s_views','total_video_retention_graph','total_video_reactions_by_type_total','total_video_views_unique']:
        r=get(vid+'/video_insights',metric=m); out['video:'+m]=kurz(r) if not (r['ok'] and m=='total_video_retention_graph') else (str(r['d'].get('data',[{}])[0].get('values',[{}])[0].get('value'))[:200] if r['d'].get('data') else 'leer')
P=get(pid+'/posts',fields='id,shares,comments.summary(true).limit(0),reactions.summary(true).limit(0)',limit=3)
out['beitrag:felder']=[(p.get('shares',{}).get('count'),p.get('comments',{}).get('summary',{}).get('total_count'),p.get('reactions',{}).get('summary',{}).get('total_count')) for p in P.get('d',{}).get('data',[])] if P['ok'] else P['f']
if P['ok'] and P['d'].get('data'):
    pi=P['d']['data'][0]['id']
    for m in ['post_clicks_by_type','post_video_avg_time_watched','post_video_view_time','post_video_complete_views_30s','post_video_retention_graph','post_reactions_by_type_total','post_media_view']:
        out['beitrag:'+m]=kurz(get(pi+'/insights',metric=m))
ig=get(pid,fields='instagram_business_account')['d'].get('instagram_business_account',{}).get('id')
for m in ['reach','views','accounts_engaged','total_interactions','likes','comments','shares','saves','profile_links_taps','follows_and_unfollows','follower_demographics']:
    out['ig:'+m]=kurz(get(ig+'/insights',metric=m,period='day',metric_type='total_value'))
M=get(ig+'/media',fields='id,media_product_type,timestamp',limit=5)
for x in M.get('d',{}).get('data',[]):
    if x.get('media_product_type')=='REELS':
        out['ig-reel']=kurz(get(x['id']+'/insights',metric='views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time,ig_reels_video_view_total_time,total_interactions'));break
s=json.dumps({'stand':dt.datetime.now().isoformat(timespec='minutes'),'tests':out},ensure_ascii=False,indent=1)
assert tok not in s and tok0 not in s
open('fb/insights-test.json','w').write(s); print(s)

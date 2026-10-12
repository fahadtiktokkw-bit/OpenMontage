"""Save completed media, an embed snippet, and the site's video index."""
import base64
import html
import json
import os
from pathlib import Path
import subprocess

BASE=Path(__file__).resolve().parent
def api(endpoint,method='GET',payload=None):
    args=['gh','api',endpoint]
    if method!='GET': args+=['--method',method,'--input','-']
    r=subprocess.run(args,input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True)
    if r.returncode:
        if method=='GET' and '404' in r.stderr:return None
        raise RuntimeError(r.stderr)
    return json.loads(r.stdout)
def main():
    repo=os.environ['GITHUB_REPOSITORY']
    run_id=os.environ['GITHUB_RUN_ID']
    videos=list((BASE/'output').rglob('almusaileem-15s.mp4'))
    if len(videos)!=1: raise ValueError('Expected exactly one completed video')
    video=videos[0]
    report=json.loads((video.parent/'report.json').read_text())
    folder='almusaileem-video/published/'+run_id
    base='https://raw.githubusercontent.com/'+repo+'/main/'+folder+'/'
    urls={'video':base+'almusaileem-15s.mp4','poster':base+'poster.jpg'}
    title=report.get('title','فيديو ديكور من المسيليم')
    snippet='<section dir="rtl"><h2>'+html.escape(title)+'</h2><video controls playsinline preload="metadata" poster="'+urls['poster']+'" style="display:block;width:100%;max-width:480px;margin:16px auto;border-radius:12px"><source src="'+urls['video']+'" type="video/mp4"></video></section>'
    (video.parent/'embed.html').write_text(snippet,encoding='utf8')
    (video.parent/'permanent-links.json').write_text(json.dumps(urls,indent=2))
    for name in ['almusaileem-15s.mp4','poster.jpg','report.json','embed.html']:
        file=video.parent/name
        if file.stat().st_size>25*1024*1024:raise ValueError('Publishing limit is 25 MB per file')
        endpoint='repos/'+repo+'/contents/'+folder+'/'+name
        if api(endpoint) is not None:continue
        api(endpoint,'PUT',{'message':'Save Almusaileem video '+run_id,'branch':'main','content':base64.b64encode(file.read_bytes()).decode()})
    gallery=os.environ.get('REQUEST_GALLERY','true').lower()=='true'
    # A failed voice attempt is preserved for review, but not showcased automatically.
    if report.get('voice_mode')=='edge' and not report.get('audible_voice'):
        gallery=False
    if gallery:
        endpoint='repos/'+repo+'/contents/almusaileem-video/published/index.json'
        old=api(endpoint)
        items=json.loads(base64.b64decode(old['content'])) if old else []
        entry={'id':run_id,'title':title,**urls,'illustrative':report.get('illustrative',False)}
        if not any(str(x.get('id'))==run_id for x in items):
            items.insert(0,entry)
            payload={'message':'Update Almusaileem video gallery','branch':'main','content':base64.b64encode(json.dumps(items,ensure_ascii=False,indent=2).encode()).decode()}
            if old:payload['sha']=old['sha']
            api(endpoint,'PUT',payload)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
        f.write('### Video ready\n\n[Download video]('+urls['video']+')\n\n')
        f.write('Gallery update: '+('included' if gallery else 'not included')+'\n')
        if report.get('voice_mode')=='edge' and not report.get('audible_voice'):
            f.write('Free TTS failed. Upload a recording; this silent fallback was not added to the website gallery.\n')
if __name__=='__main__':main()

"""Read manual GitHub inputs; use only existing media and free services."""
import ipaddress
import json
import os
from pathlib import Path
import socket
import urllib.parse
import urllib.request

BASE = Path(__file__).resolve().parent
def validate_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError('Use a public HTTPS media URL')
    for item in socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError('Private network addresses are not supported')

class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download(url,target,limit=25*1024*1024):
    validate_url(url)
    opener=urllib.request.build_opener(PublicRedirect())
    temporary=target.with_suffix(target.suffix+'.tmp')
    total=0
    try:
        with opener.open(urllib.request.Request(url,headers={'User-Agent':'AlmusaileemVideo/1.0'}),timeout=30) as response, temporary.open('wb') as f:
            while chunk:=response.read(65536):
                total+=len(chunk)
                if total>limit: raise ValueError('Media file exceeds 25 MB')
                f.write(chunk)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)

def triple(value,label):
    parts=[p.strip() for p in value.split('|')]
    if len(parts)!=3 or any(not p for p in parts):
        raise ValueError(label+' must contain 3 values separated by |')
    return parts

def main():
    from PIL import Image
    cfg=json.loads((BASE/'config.json').read_text(encoding='utf8'))
    topic=os.environ.get('REQUEST_TOPIC','').strip()
    script=os.environ.get('REQUEST_SCRIPT','').strip()
    if topic: cfg['subject']=topic
    if script: cfg['script']=script
    for key,field in [('REQUEST_TITLES','title'),('REQUEST_DETAILS','detail')]:
        if value:=os.environ.get(key,'').strip():
            for scene,value in zip(cfg['scenes'],triple(value,key)):
                scene[field]=value
    if value:=os.environ.get('REQUEST_IMAGES','').strip():
        for i,(scene,url) in enumerate(zip(cfg['scenes'],triple(value,'Image URLs')),1):
            path=BASE/'assets'/f'input-{i}.png'
            download(url,path)
            with Image.open(path) as im:
                im.load()
                if im.width<480 or im.height<480:
                    raise ValueError('Images must be at least 480 pixels on each side')
            scene['image']=str(path.relative_to(BASE))
    if url:=os.environ.get('REQUEST_AUDIO','').strip():
        download(url,BASE/'assets/voice.wav')
    cfg['illustrative']=os.environ.get('REQUEST_ILLUSTRATIVE','true').lower()=='true'
    (BASE/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__': main()

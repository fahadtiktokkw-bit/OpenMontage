"""Free-only, fixed 15-second MoneyPrinterTurbo render. No paid APIs or secrets."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

BASE = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get('MPT_ENGINE', BASE / 'engine')).resolve()
OUT = BASE / 'output' / uuid.uuid4().hex
OUT.mkdir(parents=True, exist_ok=True)
warnings = []

def run(args):
    subprocess.run(args, check=True)

def seconds(file):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
        'format=duration', '-of', 'default=nw=1:nk=1', str(file)], text=True))

def within(name):
    p = (BASE / name).resolve()
    if not p.is_relative_to(BASE):
        raise ValueError('Asset must be inside the project')
    return p

def main():
    from PIL import Image, ImageDraw, ImageFont
    cfg = json.loads((BASE / 'config.json').read_text(encoding='utf8'))
    scenes = cfg['scenes']
    if len(scenes) != 3:
        raise ValueError('This template requires exactly 3 scenes')
    mode = os.environ.get('VOICE_MODE', 'edge')
    if mode not in {'edge', 'uploaded', 'silent'}:
        raise ValueError('Unknown voice mode')
    audio = OUT / 'timeline.wav'
    source = None
    if mode == 'uploaded':
        source = BASE / 'assets/voice.wav'
        if not source.is_file():
            raise ValueError('Upload your recording to assets/voice.wav first')
    elif mode == 'edge':
        import edge_tts
        source = OUT / 'voice.mp3'
        async def speak():
            await edge_tts.Communicate(cfg['script'], 'ar-KW-FahedNeural',
                rate='+0%').save(str(source))
        try:
            asyncio.run(asyncio.wait_for(speak(), timeout=40))
            if seconds(source) <= 0:
                raise ValueError('Empty audio')
        except Exception as exc:
            source = None
            warnings.append('Free male TTS failed; video is silent. '
                            'Use uploaded voice for natural narration. ' + type(exc).__name__)
    if source is None:
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
             'anullsrc=r=44100:cl=mono', '-t', '15', str(audio)])
    else:
        length = seconds(source)
        if length > 18:
            raise ValueError('Recording is longer than 18 seconds; shorten it before rendering')
        filters = f'atempo={length/14.7:.6f},' if length > 14.7 else ''
        run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-af',
             filters + 'apad,atrim=duration=15', '-t', '15', str(audio)])
    local = ENGINE / 'storage/local_videos'
    local.mkdir(parents=True, exist_ok=True)
    run_id = 'free-' + uuid.uuid4().hex
    material_names = []
    for i, scene in enumerate(scenes, 1):
        source_image = within(scene['image'])
        with Image.open(source_image) as im:
            im.load()
        target = local / f'{run_id}-{i}{source_image.suffix}'
        temporary = target.with_suffix(target.suffix + '.tmp')
        shutil.copyfile(source_image, temporary)
        os.replace(temporary, target)
        with Image.open(target) as im:
            im.load()
        material_names.append(target.name)
        label = Image.new('RGBA', (1080, 1920))
        draw = ImageDraw.Draw(label)
        def text(y, value, size, color, bold=False):
            font = ImageFont.truetype(str(BASE / 'assets/fonts' /
                    ('Tajawal-Bold.ttf' if bold else 'Tajawal-Regular.ttf')), size)
            draw.text((540,y), value, font=font, fill=color, anchor='mm',
                      direction='rtl' if any('\u0600' <= c <= '\u06ff' for c in value) else 'ltr')
        draw.rounded_rectangle((60,115,1020,305),24,fill=(245,241,233,245))
        text(177,scene['title'],52,'#233e35',True)
        text(253,scene['detail'],36,'#233e35')
        draw.rounded_rectangle((110,1560,970,1780),28,fill=(28,58,47,245))
        text(1620,'المسيليم للأصباغ والديكور',39,'white',True)
        text(1690,'للاستفسار: 56510526',45,'white',True)
        text(1744,'@almusaileempaint',28,'white')
        if cfg.get('illustrative',False):
            draw.rounded_rectangle((350,1810,730,1860),15,fill=(245,241,233,235))
            text(1835,'تصور توضيحي',25,'#233e35')
        label.save(OUT / f'label-{i}.png')
    # No LLM/material/music providers: user text + local images + custom audio.
    if not (ENGINE / 'config.toml').exists():
        (ENGINE / 'config.toml').write_text('[app]\nffmpeg_path="/usr/bin/ffmpeg"\nenable_redis=false\n',encoding='utf8')
    sys.path.insert(0,str(ENGINE))
    os.chdir(ENGINE)
    from app.models.schema import VideoParams, MaterialInfo
    from app.services import task
    params = VideoParams(video_subject=cfg.get('subject','مايكروسمنت فوق السيراميك'),
        video_script=cfg['script'],video_source='local',video_aspect='9:16',
        video_concat_mode='sequential',video_clip_duration=5,n_threads=2,
        video_materials=[MaterialInfo(provider='local',url=name) for name in material_names],
        custom_audio_file=str(audio),subtitle_enabled=False,bgm_type='',bgm_volume=0)
    result=task.start(run_id,params,allow_server_file_input=True)
    if not result or not result.get('videos'):
        raise RuntimeError('MoneyPrinterTurbo render failed; inspect the job log')
    if len(result.get('materials', [])) != 3:
        raise RuntimeError('A scene was skipped; refusing to deliver an incomplete video')
    inputs=['ffmpeg','-y','-v','error','-i',result['videos'][0]]
    for i in range(1,4):
        inputs += ['-loop','1','-i',str(OUT / f'label-{i}.png')]
    graph="[0:v][1:v]overlay=enable='lt(t,5)'[v1];[v1][2:v]overlay=enable='gte(t,5)*lt(t,10)'[v2];[v2][3:v]overlay=enable='gte(t,10)'[out]"
    with Image.open(within(scenes[-1]['image'])) as poster:
        poster.convert('RGB').save(OUT/'poster.jpg',quality=90)
    video=OUT / 'almusaileem-15s.mp4'
    run(inputs+['-filter_complex',graph,'-map','[out]','-map','0:a:0',
        '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
        '-threads','2','-c:a','copy','-t','15','-movflags','+faststart',str(video)])
    run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'])
    if abs(seconds(video)-15) > .05:
        raise RuntimeError('Unexpected output duration')
    report={'status':'success','duration_seconds':seconds(video),
            'voice_mode':mode,'audible_voice':source is not None,'warnings':warnings,
            'paid_api_calls':0,'title':cfg.get('subject','مايكروسمنت فوق السيراميك'),
            'illustrative':cfg.get('illustrative',False)}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for p in OUT.glob('label-*.png'): p.unlink()
    for name in ['timeline.wav','voice.mp3']:
        (OUT/name).unlink(missing_ok=True)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    try: main()
    except Exception as exc:
        (OUT/'error.txt').write_text(f'{type(exc).__name__}: {exc}',encoding='utf8')
        raise

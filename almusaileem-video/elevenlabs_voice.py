"""ElevenLabs narration using included credits only; no purchases or overages."""
import json
import os
import re
from pathlib import Path
import urllib.error
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('ElevenLabs redirect refused')

def request(path, key, payload=None):
    body=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request('https://api.elevenlabs.io'+path,data=body,
        headers={'xi-api-key':key,'Content-Type':'application/json','Accept':'audio/mpeg' if payload else 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=60) as response:
            result=response.read(8*1024*1024+1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError('ElevenLabs HTTP '+str(exc.code)+'. Check key permissions, voice access and credits; no automatic retry.') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('ElevenLabs connection failed; no automatic retry.') from None
    if len(result)>8*1024*1024:raise RuntimeError('ElevenLabs response exceeded the size limit')
    return result if payload is not None else json.loads(result)

def budget(subscription,text):
    # These videos advertise a business; free-tier output lacks a commercial license.
    if subscription.get('tier') not in {'starter','creator','pro','scale','business','enterprise'}:
        raise RuntimeError('A current commercially licensed ElevenLabs plan is required. Free-tier speech is not published for business use. No upgrade was purchased.')
    if subscription.get('status')!='active':
        raise RuntimeError('ElevenLabs subscription is not active')
    extension=subscription.get('max_credit_limit_extension',
        subscription.get('max_character_limit_extension'))
    if extension != 0:
        raise RuntimeError('Disable ElevenLabs usage-based billing/credit overages before using this integration')
    count=subscription.get('character_count');limit=subscription.get('character_limit')
    if type(count) is not int or type(limit) is not int or count<0 or limit<count:
        raise RuntimeError('Could not verify the included ElevenLabs credit balance')
    # Multilingual v2: standard voice uses one credit per character, with a reserve.
    if limit-count<len(text)+100:
        raise RuntimeError('Insufficient included ElevenLabs credits; generation stopped without purchasing credits')
    return limit-count

def generate(text,target):
    key=os.environ.get('ELEVENLABS_API_KEY','').strip()
    voice=os.environ.get('ELEVENLABS_VOICE_ID','').strip()
    if not key:raise RuntimeError('Add ELEVENLABS_API_KEY in GitHub Actions secrets')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',voice):
        raise RuntimeError('Set the approved male Arabic ELEVENLABS_VOICE_ID')
    if not text.strip() or len(text)>350:
        raise ValueError('Use a short narration, at most 350 characters, for this 15-second template')
    budget(request('/v1/user/subscription',key),text)
    info=request('/v1/voices/'+voice,key)
    if (info.get('labels') or {}).get('gender','').lower()!='male':
        raise RuntimeError('Choose an approved male voice for Almusaileem')
    sharing=info.get('sharing') or {}
    if sharing.get('financial_rewards_enabled') or sharing.get('rate') not in (None,0):
        raise RuntimeError('Voice has a custom rate; choose a standard-rate voice')
    if info.get('category')!='premade' and not info.get('is_owner'):
        raise RuntimeError('Use a premade or owned standard-rate voice')
    remaining=budget(request('/v1/user/subscription',key),text)
    audio=request('/v1/text-to-speech/'+voice+'?output_format=mp3_44100_128',key,
        {'text':text,'model_id':'eleven_multilingual_v2',
         'voice_settings':{'stability':0.45,'similarity_boost':0.75,'style':0.15,'use_speaker_boost':True}})
    if not audio:raise RuntimeError('ElevenLabs returned empty audio')
    Path(target).write_bytes(audio)
    return {'provider':'elevenlabs','model':'eleven_multilingual_v2',
        'included_credits_before':remaining,'overages_enabled':False,
        'generation_requests':1,'new_purchases':0}

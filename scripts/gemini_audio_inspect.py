import json
from google import genai
from google.genai import types

CONFIG_PATH = 'config/api_keys.json'

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

client = genai.Client(api_key=cfg['gemini_api_key'])
config = types.GenerateContentConfig(
    responseModalities=['AUDIO'],
    speechConfig=types.SpeechConfig(
        voiceConfig=types.VoiceConfig(
            prebuiltVoiceConfig=types.PrebuiltVoiceConfig(voiceName='Charon')
        )
    )
)
resp = client.models.generate_content(
    model='models/gemini-2.5-flash-preview-tts',
    contents='Hello from Jarvis. This is a test of audio output.',
    config=config
)

print('RESP_TYPE', type(resp))
print('TEXT', getattr(resp, 'text', None))
print('PARTS_COUNT', len(resp.parts) if getattr(resp, 'parts', None) else None)
for idx, part in enumerate(resp.parts or []):
    print('PART_INDEX', idx)
    print('PART_TYPE', type(part))
    print('PART_DIR', [a for a in dir(part) if not a.startswith('_')])
    d = part.dict()
    print('PART_DICT_KEYS', list(d.keys()))
    print('PART_DICT_SUMMARY', {k: d[k] for k in d if k in ['value', 'inlineData', 'fileData', 'text', 'videoMetadata', 'mediaResolution', 'partMetadata']})
    if d.get('inlineData') is not None:
        inline = d['inlineData']
        print('INLINE_TYPE', type(inline))
        try:
            print('INLINE_LEN', len(inline))
        except Exception as e:
            print('INLINE_LEN_ERROR', e)
        print('INLINE_REPR', repr(inline)[:500])
    if d.get('fileData') is not None:
        filedata = d['fileData']
        print('FILEDATA_TYPE', type(filedata))
        print('FILEDATA_REPR', repr(filedata)[:500])

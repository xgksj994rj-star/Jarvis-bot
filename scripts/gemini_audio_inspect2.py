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
    inline_data = getattr(part, 'inline_data', None)
    print('INLINE_DATA_TYPE', type(inline_data))
    print('INLINE_DATA_LEN', len(inline_data) if inline_data is not None and hasattr(inline_data, '__len__') else None)
    print('INLINE_DATA_REPR', repr(inline_data)[:1000])
    print('TEXT_ATTR', getattr(part, 'text', None))
    print('FILE_DATA_TYPE', type(getattr(part, 'file_data', None)))
    print('---')

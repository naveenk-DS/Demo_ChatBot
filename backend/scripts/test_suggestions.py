import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.schemas import ChatRequest
from backend.app.main import chat

suggestions = [
    ('Show me 2BHK details', 'document_qa', True),
    ('What are the 3BHK bedroom dimensions?', 'document_qa', True),
    ('Give me 4BHK specifications', 'document_qa', True),
    ('Compare 2BHK and 3BHK', 'document_qa', True),
    ('Show bedroom images', 'media_request', False),
]

print('Testing 5 Suggested Questions against backend...')
all_ok = True
for q, exp_intent, exp_cards in suggestions:
    req = ChatRequest(message=q, history=[], provider='gemini')
    resp = chat(req)
    intent = resp.get('filters', {}).get('intent')
    cards_count = len(resp.get('properties', []))
    images_count = len(resp.get('images', []))
    has_cards = cards_count > 0
    ok = (intent == exp_intent) and (has_cards == exp_cards or (exp_intent == 'media_request' and images_count > 0))
    if not ok:
        all_ok = False
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] "{q}" -> Intent: {intent}, Cards: {cards_count}, Images: {images_count}')

print(f'\nResult: {"ALL SUGGESTED QUESTIONS PASSED" if all_ok else "SOME FAILED"}')


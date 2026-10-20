"""Small curated corpus with deterministic, inspectable lexical retrieval."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from service_intents import identify_need

VERSION = 'ltc-topic-retrieval-0.5.0'


class ServiceKnowledge:
    def __init__(self):
        raw = (Path(__file__).parent / 'knowledge.json').read_bytes()
        self.data = json.loads(raw)
        self.sha256 = hashlib.sha256(raw).hexdigest()

    def explain(self, text):
        text = unicodedata.normalize('NFKC', text)
        need = identify_need(text)
        if need:
            available={s['id'] for s in self.data['sources']}
            return [{'id':sid,'score':100-index,'matched_keywords':[],
                     'matched_topics':need['matched_terms'],'intent':need['key']}
                    for index,sid in enumerate(need['sources']) if sid in available][:3]
        ranked = []
        for order, source in enumerate(self.data['sources']):
            required = source.get('required_pattern')
            if required and not re.search(required, text):
                continue
            keywords = [t for t in source['keywords'] if t in text]
            anchors = [m.group() for pattern in source.get('topic_patterns', []) for m in re.finditer(pattern, text)]
            score = 10 * len(anchors) + len(keywords)
            if score:
                ranked.append({'source': source, 'score': score, 'matched_keywords': keywords,
                               'matched_topics': anchors, 'order': order})
        ranked.sort(key=lambda x: (-x['score'], x['order']))
        return [{'id': r['source']['id'], 'score': r['score'], 'matched_keywords': r['matched_keywords'],
                 'matched_topics': r['matched_topics']} for r in ranked[:3]]

    def retrieve(self, text):
        by_id = {s['id']: s for s in self.data['sources']}
        return [by_id[r['id']] for r in self.explain(text)]

"""Collect public species inventory and official reference phenology; read-only."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_data_integrity import read_settings
from scripts.supabase_data import load_rows, read_session

OUT = ROOT / 'data' / 'maintenance'
FOREST = 'https://nativetree.forest.gov.tw/Tree'
PDF_URL = 'https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf'


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.parts, self.anchor, self.label, self.hidden = {}, [], None, [], 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'a':
            self.anchor, self.label = attrs.get('href'), []
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'a' and self.anchor:
            if '/Tree/Info/' in self.anchor:
                url, label = urljoin(FOREST, self.anchor), ''.join(self.label).strip()
                if label and (url not in self.links or len(label) < len(self.links[url])):
                    self.links[url] = label
            self.anchor, self.label = None, []
    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())
            if self.anchor:
                self.label.append(data)


def canonical(name):
    return re.sub(r'\s+', '', name).replace('臺', '台')


def parse_months(text):
    """Only explicit numeric months; never infer a season or missing interval."""
    raw = re.sub(r'\s+', '', text).replace('翌年', '').replace('次年', '')
    if raw in ('全年', '全年開花', '全年結果'):
        return list(range(1, 13))
    raw = raw.replace('月份', '').replace('月', '')
    answer = set()
    for group in re.split('[、,，及與]', raw):
        if not group:
            continue
        span = re.fullmatch(r'(\d{1,2})[~～\-－至](\d{1,2})', group)
        single = re.fullmatch(r'\d{1,2}', group)
        if span:
            first, last = map(int, span.groups())
            if not 1 <= first <= 12 or not 1 <= last <= 12:
                raise ValueError('月份超出範圍')
            answer.update(range(first, last + 1) if first <= last else list(range(first, 13)) + list(range(1, last + 1)))
        elif single and 1 <= int(group) <= 12:
            answer.add(int(group))
        else:
            raise ValueError('月份格式需要人工核對')
    if not answer:
        raise ValueError('沒有明確月份')
    return sorted(answer)


def fetch_profile(url, name):
    cache = OUT / 'sources' / (url.rsplit('/', 1)[-1] + '.html')
    if not cache.exists():
        with read_session() as session:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            cache.write_text(response.content.decode('utf-8-sig'))
    document = Document()
    document.feed(cache.read_text())
    text = '\n'.join(document.parts)
    result = {'source_name': name, 'source_url': url, 'publisher': '林業及自然保育署', 'periods': {}}
    for field, kind in [('花期', 'flower'), ('果期', 'fruit')]:
        match = re.search(field + r'[：:]\s*([^；;\n]+)', text)
        if match:
            try:
                result['periods'][kind] = {'raw_period': match.group(1), 'months': parse_months(match.group(1))}
            except ValueError:
                result['periods'][kind] = {'raw_period': match.group(1), 'months': [], 'needs_review': True}
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'sources').mkdir(exist_ok=True)
    inventory_path = OUT / 'species_inventory.json'
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text())
    else:
        with read_session() as session:
            rows = load_rows(read_settings(ROOT / '.env'), session, table='tree_locations',
                             select='id,species_name,tree_type')
        counts = {}
        for row in rows:
            name = str(row['species_name'] or '').strip()
            if name:
                counts.setdefault(name, {'street': 0, 'protected': 0})
                kind = row['tree_type']
                counts[name][kind] = counts[name].get(kind, 0) + 1
        inventory = {'collected_at': datetime.now(ZoneInfo('Asia/Taipei')).isoformat(), 'species': counts}
        inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2))
    names = {canonical(name) for name in inventory['species']}
    print(f"Species inventory: {len(inventory['species'])} names", flush=True)
    with read_session() as session:
        response = session.get(FOREST, timeout=30)
        response.raise_for_status()
        root_html = response.content.decode('utf-8-sig')
        (OUT / 'sources' / 'forest-index.html').write_text(root_html)
    document = Document()
    document.feed(root_html)
    links = {url: name for url, name in document.links.items() if canonical(name) in names}
    references, errors = [], []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_profile, url, name): url for url, name in links.items()}
        for future in as_completed(futures):
            try:
                references.append(future.result())
            except Exception:
                errors.append(futures[future])
    payload = {'collected_at': datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
               'references': sorted(references, key=lambda item: item['source_name']), 'errors': errors}
    (OUT / 'official_phenology.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f'Official matched profiles: {len(references)}; failed: {len(errors)}', flush=True)
    pdf_path = OUT / 'sources' / 'taipei-pruning-reference.pdf'
    if not pdf_path.exists():
        with read_session() as session:
            response = session.get(PDF_URL, timeout=60)
            response.raise_for_status()
            pdf_path.write_bytes(response.content)
    print('References saved; PDF requires visual review.', flush=True)


if __name__ == '__main__':
    main()

"""Public clarification records, kept separate from simulated tree operations."""
import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data' / 'treesmatch-clarifications.geojson'
SOURCE = 'https://treesmatch.gov.taipei/pkl/public/tree-map'
API = SOURCE + '/api/clarifications.geojson'


def load_snapshot(path=SNAPSHOT):
    if not path.exists():
        return {'features': [], 'updated_at': None}
    return json.loads(path.read_text(encoding='utf-8'))


def records_from_geojson(data):
    """Topic flags indicate textual mentions, never execution status or tree counts."""
    records = []
    for feature in data.get('features', []):
        p = feature['properties']
        geometry = feature.get('geometry') or {}
        coords = geometry.get('coordinates') if geometry.get('type') == 'Point' else None
        text = p.get('title', '') + '\n' + p.get('content', '')
        records.append({
            'id': str(feature['id']), 'title': p.get('title', ''),
            'published_at': p.get('published_at', ''), 'updated_at': p.get('updated_at', ''),
            'publisher': p.get('publisher', ''), 'content': p.get('content', ''),
            'location': p.get('location_label') or ('全市資訊' if p.get('is_citywide') else '未提供地點名稱'),
            'longitude': coords[0] if coords else None, 'latitude': coords[1] if coords else None,
            'destinations': p.get('destinations') or [], 'url': p.get('url', ''),
            'photos': p.get('photos') or [],
            'mentions_removal': any(w in text for w in ('移除', '砍除', '砍伐', '伐除')),
            'mentions_transplant': any(w in text for w in ('移植', '遷移', '遷植')),
        })
    return records


def filter_records(records, topic='all', query=''):
    query = (query or '').strip().casefold()
    return [r for r in records
            if (topic != 'removal' or r['mentions_removal'])
            and (topic != 'transplant' or r['mentions_transplant'])
            and (not query or query in '\n'.join(str(r.get(k, '')) for k in
                 ('title', 'content', 'location', 'publisher')).casefold())]


def refresh():
    import requests
    response = requests.get(API, timeout=60)
    response.raise_for_status()
    data = response.json()
    if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
        raise ValueError('官方回傳資料不是 GeoJSON FeatureCollection；保留原有快照')
    records_from_geojson(data)  # Validate before replacing the previous snapshot.
    SNAPSHOT.parent.mkdir(exist_ok=True)
    temporary = SNAPSHOT.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temporary.replace(SNAPSHOT)
    (SNAPSHOT.parent / 'treesmatch-provenance.json').write_text(json.dumps({
        'source': SOURCE, 'api': API, 'retrieved_at': datetime.now().astimezone().isoformat(),
        'source_updated_at': data.get('updated_at'), 'records': len(data['features']),
        'license': data.get('license'), 'location_note': data.get('location_note'),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='更新小樹保衛站官方公開說明快照；非逐株移除移植清冊')
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    snapshot = refresh() if args.download else load_snapshot()
    print(f"官方公開說明：{len(snapshot.get('features', []))} 則；來源更新：{snapshot.get('updated_at')}")

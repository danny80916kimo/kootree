"""Read official clarification records only from the configured Supabase project."""
from pathlib import Path
from functools import lru_cache
from scripts.supabase_data import load_rows, read_session

ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://treesmatch.gov.taipei/pkl/public/tree-map'

@lru_cache(maxsize=1)
def load_snapshot():
    try:
        with read_session() as client:
            rows=load_rows(session=client,table='dashboard_official_cases',select='id,feature,source_updated_at')
        features=[]
        for row in rows:
            feature=row['feature']
            if not isinstance(feature,dict) or feature.get('type')!='Feature' or str(feature.get('id'))!=str(row['id']):
                raise ValueError('官方紀錄格式不完整')
            features.append(feature)
        snapshot={'features':features,'updated_at':max((str(row.get('source_updated_at') or '') for row in rows),default='')}
        records_from_geojson(snapshot)
        return snapshot
    except (ValueError,KeyError,TypeError):
        return {'features':[],'updated_at':None,'error':'Supabase 尚未提供可讀取的官方移除／移植公開說明資料。'}

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

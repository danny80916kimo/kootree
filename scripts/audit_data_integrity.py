"""Read-only Supabase / government tree-data audit. Never writes to Supabase."""
import argparse
import hashlib
import io
import json
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pyproj import Geod, Transformer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.supabase_data import load_rows, map_tree_locations, read_session

OFFICIAL_URL = 'https://tppkl.blob.core.windows.net/blobfs/TaipeiTree.csv'
CORE = 'id,code,tree_type,species_name,lat,lng,division_name,address,region,region_remark,height,diameter,hang_tag_date,created_at'


def read_settings(path):
    settings = dict(os.environ)
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, sep, value = line.removeprefix('export ').partition('=')
        if sep:
            settings[name.strip()] = ' '.join(shlex.split(value, comments=True))
    return settings


def missing(series):
    return series.isna() | series.fillna('').astype(str).str.strip().eq('')


def valid_uuid(value):
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def profile_trees(frame):
    if frame.empty:
        return {'rows': 0}, frame.copy()
    flags = pd.DataFrame(index=frame.index)
    fields = {}
    for column in frame.columns:
        mask = missing(frame[column])
        fields[column] = {'missing': int(mask.sum()), 'present': int((~mask).sum())}
    flags['missing_code'] = missing(frame['code'])
    flags['duplicate_code'] = ~flags['missing_code'] & frame['code'].astype(str).str.strip().duplicated(keep=False)
    flags['invalid_uuid'] = ~frame['id'].map(valid_uuid)
    flags['duplicate_uuid'] = frame['id'].duplicated(keep=False)
    lat = pd.to_numeric(frame['lat'], errors='coerce')
    lng = pd.to_numeric(frame['lng'], errors='coerce')
    flags['invalid_coordinates'] = ~(lat.between(-90, 90) & lng.between(-180, 180))
    flags['outside_taipei_review_box'] = ~flags['invalid_coordinates'] & ~(lat.between(24.8, 25.3) & lng.between(121.2, 121.9))
    numeric = {}
    for column in ['height', 'diameter']:
        values = pd.to_numeric(frame[column], errors='coerce')
        flags[f'{column}_invalid_numeric'] = ~missing(frame[column]) & ~np.isfinite(values)
        flags[f'{column}_zero'] = values.eq(0)
        flags[f'{column}_negative'] = values.lt(0)
        finite = values[np.isfinite(values)]
        numeric[column] = {'zero': int(values.eq(0).sum()), 'negative': int(values.lt(0).sum()),
                           'invalid_numeric': int(flags[f'{column}_invalid_numeric'].sum()),
                           'min': float(finite.min()) if len(finite) else None,
                           'max': float(finite.max()) if len(finite) else None}
    # Review threshold only: source units must be verified before interpreting it.
    flags['height_above_100_review'] = pd.to_numeric(frame['height'], errors='coerce').gt(100)
    districts = pd.DataFrame(map_tree_locations(frame.to_dict('records')))['district']
    flags['unmapped_district'] = districts.isna().to_numpy()
    flags['missing_road'] = missing(frame['region'])
    flags['missing_species'] = missing(frame['species_name'])
    stats = {'rows': len(frame), 'fields': fields, 'flags': {col: int(flags[col].sum()) for col in flags},
             'review_thresholds': {'height_above_100_review': 'Raw height > 100; review source units/value, not an automatic correction.'},
             'duplicate_code_groups': int(frame.loc[flags['duplicate_code'], 'code'].nunique()),
             'numeric': numeric, 'district_counts': districts.fillna('未提供').value_counts().to_dict()}
    problem = flags.any(axis=1)
    anomalies = frame.loc[problem, ['id', 'code', 'tree_type', 'lat', 'lng', 'height', 'diameter', 'region']].copy()
    anomalies['audit_flags'] = flags.loc[problem].apply(lambda row: ','.join(row.index[row]), axis=1)
    return stats, anomalies


def compare_official(street, official, output):
    cloud = street.copy()
    cloud['code'] = cloud['code'].fillna('').astype(str).str.strip()
    source = official.copy()
    source['TreeID'] = source['TreeID'].fillna('').astype(str).str.strip()
    cloud_codes = set(cloud['code']) - {''}
    source_codes = set(source['TreeID']) - {''}
    cloud.loc[~cloud['code'].isin(source_codes)].to_csv(output / 'supabase_only.csv', index=False, encoding='utf-8-sig')
    source.loc[~source['TreeID'].isin(cloud_codes)].to_csv(output / 'official_only.csv', index=False, encoding='utf-8-sig')
    cloud_unique = cloud[cloud['code'].ne('') & ~cloud['code'].duplicated(keep=False)]
    source_unique = source[source['TreeID'].ne('') & ~source['TreeID'].duplicated(keep=False)]
    pairs = cloud_unique.merge(source_unique, left_on='code', right_on='TreeID', validate='one_to_one')
    pairs['mapped_district'] = [row['district'] for row in map_tree_locations(pairs.to_dict('records'))]
    comparisons = [('species_name', 'TreeType'), ('mapped_district', 'Dist'), ('region', 'Region'),
                   ('height', 'TreeHeight'), ('diameter', 'Diameter')]
    mismatches = []
    counts = {}
    for cloud_col, official_col in comparisons:
        left, right = pairs[cloud_col], pairs[official_col]
        if cloud_col in ['height', 'diameter']:
            a, b = pd.to_numeric(left, errors='coerce'), pd.to_numeric(right, errors='coerce')
            equal = pd.Series(np.isclose(a, b, atol=1e-6, rtol=0, equal_nan=False), index=pairs.index)
            equal |= missing(left) & missing(right)
        else:
            equal = left.fillna('').astype(str).str.strip().eq(right.fillna('').astype(str).str.strip())
        different = ~equal
        counts[cloud_col] = int(different.sum())
        delta = pairs.loc[different, ['id', 'code']].copy()
        delta['field'] = cloud_col
        delta['supabase_value'] = left[different].astype(str)
        delta['official_value'] = right[different].astype(str)
        mismatches.append(delta)
    a = pairs['species_name'].fillna('').astype(str).str.strip().str.replace('臺', '台', regex=False)
    b = pairs['TreeType'].fillna('').astype(str).str.strip().str.replace('臺', '台', regex=False)
    counts['species_after_tai_character_normalization'] = int(a.ne(b).sum())
    transformer = Transformer.from_crs('EPSG:3826', 'EPSG:4326', always_xy=True)
    official_lon, official_lat = transformer.transform(pd.to_numeric(pairs['TWD97X'], errors='coerce').to_numpy(),
                                                       pd.to_numeric(pairs['TWD97Y'], errors='coerce').to_numpy())
    _, _, distance = Geod(ellps='WGS84').inv(pd.to_numeric(pairs['lng'], errors='coerce').to_numpy(),
                                           pd.to_numeric(pairs['lat'], errors='coerce').to_numpy(), official_lon, official_lat)
    distances = pairs[['id', 'code', 'lat', 'lng']].copy()
    distances['official_lat'] = official_lat
    distances['official_lng'] = official_lon
    distances['distance_metres'] = distance
    distances.loc[~np.isfinite(distance) | (distance > 10)].to_csv(output / 'coordinate_differences.csv', index=False, encoding='utf-8-sig')
    changes = pd.concat(mismatches, ignore_index=True)
    changes.to_csv(output / 'field_differences.csv', index=False, encoding='utf-8-sig')
    coordinate_ids = set(distances.loc[~np.isfinite(distance) | (distance > 10), 'id'])
    return {'official_rows': len(source), 'official_duplicate_id_rows': int(source['TreeID'].duplicated(keep=False).sum()),
            'cloud_unique_codes': len(cloud_codes), 'official_unique_codes': len(source_codes),
            'codes_in_both': len(cloud_codes & source_codes), 'supabase_only_codes': len(cloud_codes - source_codes),
            'official_only_codes': len(source_codes - cloud_codes), 'unambiguous_compared_pairs': len(pairs),
            'unique_trees_with_field_differences': int(changes['id'].nunique()),
            'unique_trees_with_any_compared_difference': len(set(changes['id']) | coordinate_ids),
            'field_mismatches': counts, 'coordinates_over_10m': int((distance > 10).sum()),
            'coordinates_over_50m': int((distance > 50).sum()), 'coordinates_over_100m': int((distance > 100).sum()),
            'invalid_coordinate_pairs': int((~np.isfinite(distance)).sum())}


def profile_reports(frame, trees, demo=False):
    if frame.empty:
        return {'rows': 0}
    referenced = frame['tree_location_id'].astype(str)
    all_ids = set(trees['id'].astype(str))
    street_ids = set(trees.loc[trees['tree_type'].eq('street'), 'id'].astype(str))
    created = pd.to_datetime(frame['created_at'], errors='coerce', utc=True, format='mixed')
    confirmed = pd.to_datetime(frame['confirmed_at'], errors='coerce', utc=True, format='mixed')
    result = {'rows': len(frame), 'duplicate_id_rows': int(frame['id'].duplicated(keep=False).sum()),
              'orphan_tree_references': int((~referenced.isin(all_ids)).sum()),
              'street_reports': int(referenced.isin(street_ids).sum()),
              'other_tree_reports': int((referenced.isin(all_ids) & ~referenced.isin(street_ids)).sum()),
              'invalid_created_dates': int(created.isna().sum()),
              'future_created_dates': int(created.gt(pd.Timestamp.now(tz='UTC')).sum()),
              'invalid_confirmation_dates': int((~missing(frame['confirmed_at']) & confirmed.isna()).sum()),
              'confirmation_before_creation': int(confirmed.lt(created).sum()),
              'missing_type': int(missing(frame['type']).sum()),
              'missing_dismissed_flag': int(frame['dismissed'].isna().sum()),
              'pending': int((frame['dismissed'].eq(False) & confirmed.isna()).sum()),
              'confirmed': int((frame['dismissed'].eq(False) & confirmed.notna()).sum()),
              'dismissed': int(frame['dismissed'].eq(True).sum())}
    if demo:
        score = pd.to_numeric(frame['risk_score'], errors='coerce')
        level = score.map(lambda n: '高' if n >= 70 else '中' if n >= 40 else '低')
        result.update({'missing_simulation_labels': int(frame['is_simulated'].ne(True).sum()),
                       'invalid_risk_scores': int((~score.between(0, 100)).sum()),
                       'risk_level_mismatches': int(level.ne(frame['risk_level']).sum()),
                       'high_risk_rows': int(frame['risk_level'].eq('高').sum()),
                       'batch_counts': frame['simulation_batch'].value_counts().to_dict()})
    return result


def write_report(summary, output):
    street, comparison = summary['street'], summary['comparison']
    flags, official = street['flags'], summary['official_source']
    mismatches = comparison['field_mismatches']
    def link(name):
        return f'[{name}]({output.resolve() / name})'
    text = f'''# Kootree 資料完整性稽核

稽核時間（臺北）：{summary['audited_at_taipei']}。本次唯讀檢查，未修改雲端資料。

## 結論

樹籍的核心欄位已可完整分頁讀取，仍存在資料缺漏、數值疑點及政府版本差異。現階段適合展示與資料探索；作為正式管理依據前，需要逐筆複核下列清單。

## 範圍與讀取結果

| 範圍 | 筆數 |
|---|---:|
| 行道樹 | {street['rows']:,} |
| 受保護樹木 | {summary['protected']['rows']:,} |
| 真實通報 | {summary.get('tree_reports', {}).get('rows', '讀取失敗')} |
| 模擬通報 | {summary.get('dashboard_demo_reports', {}).get('rows', '讀取失敗')} |
| 樹木狀態 view | {summary.get('tree_status_view', {}).get('rows', '讀取失敗')} |

全量檢查目前 API 金鑰可見的樹籍與通報核心資料；未取得管理員快照，也未讀取市民身分、照片或原始通報文字。分頁讀取期間檢查筆數一致性，但不代表資料庫交易快照。沒有檢查 App 私人帳本或其他非後台用途資料表。

## 行道樹品質

| 項目 | 結果 |
|---|---:|
| 缺樹號 | {flags['missing_code']:,} |
| 重複樹號列數 | {flags['duplicate_code']:,} |
| 無效／重複 UUID 列數 | {flags['invalid_uuid']:,} / {flags['duplicate_uuid']:,} |
| 無效經緯度／超出臺北檢核框 | {flags['invalid_coordinates']:,} / {flags['outside_taipei_review_box']:,} |
| 無法辨識行政區 | {flags['unmapped_district']:,} |
| 缺路段 | {flags['missing_road']:,} |
| 樹種欄位空值 | {flags['missing_species']:,} |
| 樹高為 0 | {flags['height_zero']:,} |
| 胸徑為 0 | {flags['diameter_zero']:,} |
| 原始樹高大於 100，需複核 | {flags.get('height_above_100_review', '未統計')} |

樹高及胸徑都有欄位值，但 0 值及離群值仍需確認。樹高最大原始值為 **{street['numeric']['height']['max']}**，不可直接當作可信量測。大於 100 是人工複核門檻，尚未確認來源單位，不能據此自動改小數點或判定樹木安全。離群清單為 {link('height_outliers.csv')}。

路段缺漏與量測疑點詳見 {link('street_anomalies.csv')}。行道樹 `address` 與 `hang_tag_date` 全空，目前以 `region` 表示路段。受保護樹木的 `region` 全空但 `address` 有值，兩類資料需採不同欄位規則；受保護樹木不在目前行道樹後台統計範圍。

實際 `tree_locations` 沒有調查日期欄位。`created_at` 是資料建立時間、`hang_tag_date` 是掛牌日期，均不可代替調查日期。官方 CSV 仍有 {official.get('survey_date_unparseable', '未統計')} 筆缺漏／無法解析的調查日期，以及 {official.get('survey_date_1900_placeholder_review', '未統計')} 筆 `1900-01-01` 日期需複核。

## 與政府現行公開 CSV 全量比對

官方網址：{OFFICIAL_URL}

本次下載時間：{official['downloaded_at_taipei']}；伺服器 Last-Modified：{official['last_modified']}。官方檔案 SHA-256 記錄於 {link('summary.json')}，完整下載快照為 {link('official_snapshot.csv')}。與本機原始 CSV 位元組是否一致：{official['same_as_local_raw_bytes']}。

| 樹號對照 | 數量 |
|---|---:|
| 官方 CSV | {comparison['official_rows']:,} |
| 兩邊都有的樹號 | {comparison['codes_in_both']:,} |
| 僅 Supabase 有 | {comparison['supabase_only_codes']:,} |
| 僅官方有 | {comparison['official_only_codes']:,} |

目前涵蓋官方樹號的 {comparison['codes_in_both'] / comparison['official_unique_codes'] * 100:.2f}%。Supabase 額外的樹號不能直接視為錯誤或刪除，可能涉及新增、移除或來源版本差異，須由管理者確認。清單：{link('supabase_only.csv')}、{link('official_only.csv')}。

兩邊可一對一對照的 {comparison['unambiguous_compared_pairs']:,} 筆中：

| 欄位 | 不一致筆數 |
|---|---:|
| 樹種 | {mismatches['species_name']:,} |
| 行政區 | {mismatches['mapped_district']:,} |
| 路段 | {mismatches['region']:,} |
| 樹高原始值 | {mismatches['height']:,} |
| 胸徑原始值 | {mismatches['diameter']:,} |
| 座標差距大於 10 公尺 | {comparison['coordinates_over_10m']:,} |

欄位差異可能同時落在同一棵樹，不能將上述筆數相加當作不同樹木數量。座標已從官方 TWD97 EPSG:3826 轉 WGS84，使用橢球面距離比較；10 公尺是複核門檻。詳見 {link('field_differences.csv')}、{link('coordinate_differences.csv')}。

去除重複樹木後，{comparison.get('unique_trees_with_field_differences', '未統計')} 棵存在欄位差異；連同座標差異，共 {comparison.get('unique_trees_with_any_compared_difference', '未統計')} 棵需複核。

## 通報與模擬資料

| 檢核 | 真實通報 | 模擬通報 |
|---|---:|---:|
| 筆數 | {summary.get('tree_reports', {}).get('rows', '讀取失敗')} | {summary.get('dashboard_demo_reports', {}).get('rows', '讀取失敗')} |
| 待確認 | {summary.get('tree_reports', {}).get('pending', '未統計')} | {summary.get('dashboard_demo_reports', {}).get('pending', '未統計')} |
| 已確認 | {summary.get('tree_reports', {}).get('confirmed', '未統計')} | {summary.get('dashboard_demo_reports', {}).get('confirmed', '未統計')} |
| 已排除 | {summary.get('tree_reports', {}).get('dismissed', '未統計')} | {summary.get('dashboard_demo_reports', {}).get('dismissed', '未統計')} |
| 無法對應樹木的通報 | {summary.get('tree_reports', {}).get('orphan_tree_references', '未統計')} | {summary.get('dashboard_demo_reports', {}).get('orphan_tree_references', '未統計')} |
| 無法解析建立日期 | {summary.get('tree_reports', {}).get('invalid_created_dates', '未統計')} | {summary.get('dashboard_demo_reports', {}).get('invalid_created_dates', '未統計')} |

模擬標記缺漏：{summary.get('dashboard_demo_reports', {}).get('missing_simulation_labels', '未統計')}；模擬分數／分級不一致：{summary.get('dashboard_demo_reports', {}).get('risk_level_mismatches', '未統計')}。其餘日期、關聯與狀態檢查詳見 JSON 摘要。

真實通報不在行道樹範圍，並不代表孤兒資料；本次另以全體樹木確認關聯。確認狀態不等於工單結案狀態。模擬風險只覆蓋模擬通報關聯的樹木，其餘樹木未經風險評估。物候規則尚未接入後台，沒有規則時不產生養護指令。

## 畫面與資料範圍

明細僅提供目前篩選結果前 1,000 筆供畫面分頁；地圖最多抽樣 8,000 點。KPI 與 CSV 匯出採完整篩選結果。因此畫面 84 頁（每頁 12 筆）不代表資料庫只有約 1,000 筆。稽核直接讀取全部 API 可見列，未受畫面上限影響。

## 處理順序

1. 複核 0 值及極端樹高，向來源確認單位與量測值，保留修改依據。
2. 比對僅官方／僅 Supabase 的樹號，決定新增、更新、保留或停用，避免直接刪除。
3. 補調查日期與來源更新日期，將原始值、來源版本和匯入時間分開儲存。
4. 逐筆處理欄位與座標差異，再做版本化同步；真實與模擬資料繼續分開。

讀取錯誤：`{json.dumps(summary['table_errors'], ensure_ascii=False)}`。完整機器可讀結果為 {link('summary.json')}。
'''
    (output / 'REPORT.md').write_text(text)


def run(settings, output):
    output.mkdir(parents=True, exist_ok=True)
    summary = {'audited_at_taipei': datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
               'scope': 'Current API-visible rows, not a privileged database snapshot; no remote writes.',
               'table_errors': {}}
    class Progress:
        def __init__(self, session):
            self.session, self.calls = session, 0
        def get(self, url, **kwargs):
            response = self.session.get(url, **kwargs)
            self.calls += 1
            if self.calls % 10 == 0:
                print(f'Completed {self.calls} API pages', flush=True)
            return response
    with read_session() as session:
        client = Progress(session)
        rows = load_rows(settings, client, table='tree_locations', select=CORE)
        trees = pd.DataFrame(rows)
        print(f'Read {len(trees):,} tree records', flush=True)
        summary['tree_types'] = trees['tree_type'].fillna('(null)').value_counts().to_dict()
        for kind in ['street', 'protected']:
            selected = trees[trees['tree_type'].eq(kind)].reset_index(drop=True)
            stats, anomalies = profile_trees(selected)
            summary[kind] = stats
            anomalies.to_csv(output / f'{kind}_anomalies.csv', index=False, encoding='utf-8-sig')
            if kind == 'street':
                anomalies.loc[anomalies['audit_flags'].str.contains('height_above_100_review')].to_csv(output / 'height_outliers.csv', index=False, encoding='utf-8-sig')
        reports = None
        for table, select, order in [
            ('tree_reports', 'id,tree_location_id,type,created_at,confirmed_at,dismissed', 'id'),
            ('dashboard_demo_reports', 'id,tree_location_id,type,created_at,confirmed_at,dismissed,is_simulated,risk_score,risk_level,simulation_batch,source_report_id', 'id'),
            ('tree_status_view', 'tree_location_id,status,updated_at,watch_count', 'tree_location_id'),
        ]:
            try:
                data = pd.DataFrame(load_rows(settings, client, table=table, select=select, order_column=order))
                if table == 'tree_status_view':
                    summary[table] = {'rows': len(data), 'orphan_tree_references': int((~data['tree_location_id'].isin(trees['id'])).sum()) if len(data) else 0}
                else:
                    summary[table] = profile_reports(data, trees, demo=table.startswith('dashboard_demo'))
                    if table == 'tree_reports':
                        reports = data
                    elif len(data) and reports is not None:
                        summary[table]['orphan_prototype_references'] = int((~data['source_report_id'].isin(reports['id'])).sum())
                print(f'{table}: {len(data)} rows', flush=True)
            except ValueError as error:
                summary['table_errors'][table] = str(error)
    # The current schema has no survey_date; verify keys on one live record without storing its contents.
    key = settings['SUPABASE_KEY']
    headers = {'apikey': key, 'Accept-Profile': settings.get('SUPABASE_SCHEMA', 'public')}
    if not key.startswith(('sb_secret_', 'sb_publishable_')):
        headers['Authorization'] = 'Bearer ' + key
    with read_session() as session:
        probe = session.get(settings['SUPABASE_URL'].rstrip('/') + '/rest/v1/tree_locations', headers=headers,
                            params={'select': '*', 'tree_type': 'eq.street', 'limit': 1}, timeout=30, allow_redirects=False)
        if probe.status_code in (200, 206) and probe.json():
            summary['actual_tree_columns'] = sorted(probe.json()[0].keys())
        else:
            summary['table_errors']['schema_probe'] = f'HTTP {probe.status_code}'
    print('Downloading current official CSV for full comparison...', flush=True)
    with read_session() as session:
        response = session.get(OFFICIAL_URL, timeout=60)
        response.raise_for_status()
        blob = response.content
    (output / 'official_snapshot.csv').write_bytes(blob)
    official = pd.read_csv(io.BytesIO(blob), encoding='utf-8-sig', dtype=str)
    summary['official_source'] = {'url': OFFICIAL_URL, 'sha256': hashlib.sha256(blob).hexdigest(),
                                  'last_modified': response.headers.get('Last-Modified'),
                                  'downloaded_at_taipei': datetime.now(ZoneInfo('Asia/Taipei')).isoformat(),
                                  'survey_date_missing': int(missing(official['SurveyDate']).sum()),
                                  'update_values': sorted(official['UpdDate'].dropna().unique().tolist())[-5:] if 'UpdDate' in official else []}
    survey_dates = pd.to_datetime(official['SurveyDate'], errors='coerce', format='mixed')
    summary['official_source']['survey_date_unparseable'] = int(survey_dates.isna().sum())
    summary['official_source']['survey_date_1900_placeholder_review'] = int(official['SurveyDate'].eq('1900-01-01').sum())
    summary['official_source']['height_above_100_review'] = int(pd.to_numeric(official['TreeHeight'], errors='coerce').gt(100).sum())
    official.loc[official['SurveyDate'].eq('1900-01-01') | survey_dates.isna()].to_csv(output / 'official_survey_date_review.csv', index=False, encoding='utf-8-sig')
    summary['comparison'] = compare_official(trees[trees['tree_type'].eq('street')], official, output)
    local = ROOT / 'data' / 'taipei_tree_raw.csv'
    summary['official_source']['same_as_local_raw_bytes'] = local.read_bytes() == blob
    summary['display_limits'] = {'table_rows': 1000, 'map_points': 8000,
                                  'kpi_and_export': 'complete selected population'}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    write_report(summary, output)
    print(json.dumps({name: summary[name] for name in ['tree_types', 'comparison', 'tree_reports', 'dashboard_demo_reports', 'table_errors'] if name in summary}, ensure_ascii=False, indent=2), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports' / 'data-integrity-2026-10-24')
    args = parser.parse_args()
    try:
        run(read_settings(args.env_file), args.output)
    except Exception as error:
        # Do not dump request headers, URLs containing credentials, or arbitrary server response bodies.
        print(f'Audit failed ({type(error).__name__}). No cloud data was changed.', flush=True)
        raise SystemExit(1)

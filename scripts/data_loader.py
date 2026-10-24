"""官方樹木 CSV 正規化與 TWD97 TM2 -> WGS84 轉換。"""
from pathlib import Path
import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / 'data' / 'taipei_tree_raw.csv'
CLEAN_FILE = ROOT / 'data' / 'trees_clean.csv'
SOURCE_URL = 'https://tppkl.blob.core.windows.net/blobfs/TaipeiTree.csv'


def load_csv(path):
    for encoding in ('utf-8-sig', 'utf-8', 'cp950', 'big5'):
        try:
            return pd.read_csv(path, encoding=encoding, low_memory=False, dtype={'TreeID': 'string'})
        except UnicodeDecodeError:
            continue
    raise ValueError('無法識別 CSV 編碼')


def transform_trees(df):
    required = ['TreeID', 'Dist', 'Region', 'TreeType', 'TWD97X', 'TWD97Y']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f'缺少必要欄位: {missing}')
    df = df.copy()
    df.columns = df.columns.str.strip()
    rename = {'TreeID': 'tree_id', 'Dist': 'district', 'Region': 'road',
              'RegionRemark': 'region_remark', 'TreeType': 'species',
              'Diameter': 'diameter_cm', 'TreeHeight': 'height_m',
              'SurveyDate': 'survey_date', 'Update': 'updated_at',
              'TWD97X': 'twd97_x', 'TWD97Y': 'twd97_y'}
    df = df.rename(columns=rename)
    for col in ('twd97_x','twd97_y','diameter_cm','height_m'):
        if col not in df: df[col] = None
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['twd97_x', 'twd97_y'])
    # EPSG:3826 = TWD97 / TM2 zone 121, official coordinates are metres.
    converter = Transformer.from_crs('EPSG:3826', 'EPSG:4326', always_xy=True)
    longitude, latitude = converter.transform(df['twd97_x'].to_numpy(), df['twd97_y'].to_numpy())
    df['longitude'], df['latitude'] = longitude, latitude
    df = df[df['latitude'].between(24.8,25.3) & df['longitude'].between(121.2,121.9)].copy()
    for col in ('tree_id','district','road','species','survey_date'):
        if col not in df: df[col] = ''
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['species'] = df['species'].replace('', '未分類')
    df['district'] = df['district'].replace('', '未分類')
    df['road'] = df['road'].replace('', '未記載')
    return df.reset_index(drop=True)


def prepare_data(raw_path=RAW_FILE, output_path=CLEAN_FILE):
    clean = transform_trees(load_csv(raw_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(output_path, index=False, encoding='utf-8-sig')
    return clean

if __name__ == '__main__':
    import argparse
    import requests
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true', help='下載臺北市官方 CSV')
    parser.add_argument('--input', default=str(RAW_FILE), help='自行下載的官方 CSV 路徑')
    args = parser.parse_args()
    csv_path = Path(args.input)
    if args.download:
        response = requests.get(SOURCE_URL, timeout=120)
        response.raise_for_status()
        RAW_FILE.write_bytes(response.content)
        csv_path = RAW_FILE
    clean = prepare_data(csv_path)
    print(f'成功轉換 {len(clean):,} 筆樹木資料，已儲存 {CLEAN_FILE}')

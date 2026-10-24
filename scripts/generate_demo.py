"""僅用於功能展示的虛構樹木紀錄，不代表臺北市真實樹籍。"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'demo_trees.csv'

def generate_demo_data(n=850, seed=42):
    random = np.random.default_rng(seed)
    regions = [
        ('中正區','中山南路',25.0373,121.5189),('大安區','仁愛路',25.0379,121.5430),
        ('信義區','松仁路',25.0349,121.5687),('中山區','南京東路',25.0521,121.5351),
        ('松山區','敦化北路',25.0561,121.5480),('內湖區','瑞光路',25.0776,121.5741),
        ('士林區','中山北路',25.0962,121.5250),('北投區','中央北路',25.1370,121.5042),
        ('萬華區','西園路',25.0304,121.4958),('大同區','承德路',25.0637,121.5182),
        ('南港區','南港路',25.0547,121.6043),('文山區','木柵路',24.9892,121.5632)]
    species = ['榕樹','台灣欒樹','小葉欖仁','木棉','黑板樹','樟樹','茄苳','苦楝']
    probabilities=[.22,.18,.16,.12,.10,.11,.07,.04]
    rows=[]
    for i in range(n):
        idx=int(random.integers(0,len(regions)))
        district,road,lat,lon=regions[idx]
        rows.append({'tree_id':f'DEMO-{i+1:05d}','district':district,'road':road,
            'species':str(random.choice(species,p=probabilities)),
            'diameter_cm':round(float(random.uniform(12,78)),1),
            'height_m':round(float(random.uniform(3,18)),1),
            'latitude':lat+float(random.normal(0,.0025)),
            'longitude':lon+float(random.normal(0,.003)),
            'survey_date':'2026-01-01','updated_at':'',
            'region_remark':'虛構示範資料'})
    return pd.DataFrame(rows)

if __name__=='__main__':
    generate_demo_data().to_csv(OUT,index=False,encoding='utf-8-sig')
    print(f'Generated {OUT}')

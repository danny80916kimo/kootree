"""Build reviewable SQL from the collected official sources; no cloud writes."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.care_calendar import species_key
DATA = ROOT / 'data' / 'maintenance'
PDF_URL = 'https://www-ws.gov.taipei/001/Upload/public/mmo/pkl/各式形態樹木修剪示範.pdf'
GENERAL_URL = 'https://laws.gov.taipei/law/LawSearch/LawArticleContent/FL004003'


def build_rules():
    references = json.loads((DATA / 'official_phenology.json').read_text())['references']
    seeds = []
    for source in references:
        for kind, period in source['periods'].items():
            if not period['months'] or period.get('needs_review'):
                continue
            event = '花期觀察參考' if kind == 'flower' else '果期觀察參考'
            action = '記錄當地開花與落花情況，依實際狀況維持通行空間整潔。' if kind == 'flower' else '觀察果實成熟及地面落果，依現場狀況評估清潔需求。'
            seeds.append({'species_key': species_key(source['source_name']), 'months': period['months'], 'rule_type': kind,
                          'event': event, 'action': action, 'source_urls': [source['source_url']],
                          'source_note': f"林業及自然保育署記載：{period['raw_period']}。全臺物候參考，臺北需依當年氣候及現地觀察校正；不是修剪月份。",
                          'evidence_level': 'reference', 'enabled': True})
    # Visually checked PDF pages 4,8,12,16,20,24. These are assessment windows,
    # never an instruction to execute the historical document's heavy pruning.
    for name, months, page in [
        ('榕樹', list(range(4, 11)), 4), ('樟樹', [3, 4], 4),
        ('茄苳', [1, 2, 12], 8), ('臺灣欒樹', [1, 2, 12], 8),
        ('白千層', [3, 4], 12), ('楓香', [1, 2, 12], 12),
        ('黑板樹', list(range(4, 11)), 16), ('阿勃勒', list(range(6, 11)), 20),
        ('印度紫檀', list(range(6, 11)), 20), ('大王椰子', list(range(5, 11)), 24),
        ('蒲葵', list(range(5, 11)), 24),
    ]:
        seeds.append({'species_key': species_key(name), 'months': months, 'rule_type': 'assessment',
                      'event': '季節養護評估參考', 'action': '由管理單位依樹勢、現地物候及天候評估養護需求；本提示不自動指示修剪。',
                      'source_urls': [PDF_URL + f'#page={page}'],
                      'source_note': f'臺北市公園處歷史修剪示範月曆，PDF 第 {page} 頁已目視核對。歷史參考須經現地專業評估；不是本年度施工計畫。',
                      'evidence_level': 'reference', 'enabled': True})
    seeds.extend([
        {'species_key': '木棉', 'months': [2, 3], 'rule_type': 'flower', 'event': '花期觀察參考',
         'action': '觀察開花及落花，依現場情況維持通行空間整潔。',
         'source_urls': ['https://zzdo.gov.taipei/cp.aspx?n=4603E2443E2D75D8'],
         'source_note': '臺北市中正區公所記載 2–3 月先花後葉；實際花期依當年氣候觀察。', 'evidence_level': 'reference', 'enabled': True},
        {'species_key': '木棉', 'months': [5], 'rule_type': 'fruit', 'event': '果實棉絮觀察參考',
         'action': '觀察果實及棉絮，依實際落果、棉絮情況評估清潔及通行維護。',
         'source_urls': ['https://zzdo.gov.taipei/cp.aspx?n=4603E2443E2D75D8'],
         'source_note': '區公所記載約 5 月棉絮散布；不據此自動安排摘果或修剪。', 'evidence_level': 'reference', 'enabled': True},
        {'species_key': '小葉欖仁', 'months': [], 'rule_type': 'flower', 'event': '花期資料待確認',
         'action': '官方來源記載月份不同，先建立臺北在地觀察紀錄，確認後再啟用月份規則。',
         'source_urls': ['https://kmweb.moa.gov.tw/subject/subject.php?id=27041', 'https://pwbpo.kcg.gov.tw/News_Content.aspx?n=A861811798A0B9C7&s=598D5FB950E3746F&sms=5B2116A2A2920C77'],
         'source_note': '農業知識入口網記載 3–5 月，高雄市公園處記載 9–11 月；樹種學名及區域適用性需專家核對。', 'evidence_level': 'conflict', 'enabled': False},
        {'species_key': '小葉欖仁', 'months': [], 'rule_type': 'assessment', 'event': '養護月份待現地確認',
         'action': '依當地落葉與萌芽情況評估；歷史月曆圖與文字適期不完全一致，暫不給固定月份。',
         'source_urls': [PDF_URL + '#page=16'], 'source_note': '歷史文件文字與月曆圖不完全一致；保留衝突，未啟用。', 'evidence_level': 'conflict', 'enabled': False},
    ])
    return seeds


def main():
    seeds = build_rules()
    template = (ROOT / 'supabase' / 'care_calendar_schema.sql').read_text()
    sql = template.replace('-- CARE_SEEDS_JSON', json.dumps(seeds, ensure_ascii=False, indent=2))
    (ROOT / 'supabase' / 'seed_species_care_calendar.sql').write_text(sql)
    (DATA / 'care_rule_seeds.json').write_text(json.dumps(seeds, ensure_ascii=False, indent=2))
    inventory = json.loads((DATA / 'species_inventory.json').read_text())['species']
    referenced = {row['species_key'] for row in seeds if row['enabled']}
    conflict = {row['species_key'] for row in seeds if not row['enabled']}
    rows = []
    for name, counts in inventory.items():
        applicable = [seed for seed in seeds if seed['species_key'] == species_key(name)]
        rows.append({'species_name': name, 'street_count': counts['street'], 'protected_count': counts['protected'],
                     'reference_rules': sum(row['enabled'] for row in applicable),
                     'review_status': '有月份參考，仍需現地確認' if species_key(name) in referenced else '只有全年例行觀察，專屬月份待確認',
                     'has_source_conflict': species_key(name) in conflict,
                     'reference_months': sorted({month for row in applicable if row['enabled'] for month in row['months']})})
    import pandas as pd
    pd.DataFrame(rows).to_csv(DATA / 'species_care_coverage.csv', index=False, encoding='utf-8-sig')
    summary = {'species_profiles': len(inventory), 'species_with_references': sum(bool(row['reference_rules']) for row in rows),
               'species_pending_specific_months': sum(not row['reference_rules'] for row in rows),
               'reference_rule_templates': sum(row['enabled'] for row in seeds),
               'conflicting_rule_templates': sum(not row['enabled'] for row in seeds),
               'street_trees_with_reference': sum(row['street_count'] for row in rows if row['reference_rules']),
               'street_trees_total': sum(row['street_count'] for row in rows)}
    (DATA / 'care_coverage_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

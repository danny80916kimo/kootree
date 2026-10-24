"""Source-backed observation calendar; no inferred pruning instructions."""
import re
from urllib.parse import urlparse

from scripts.supabase_data import load_rows, read_session


def species_key(name):
    return re.sub(r'\s+', '', str(name)).replace('臺', '台')


def normalize_calendar(profiles, rules):
    calendar = {}
    for row in profiles:
        name = str(row.get('species_name') or '').strip()
        if not name:
            raise ValueError('養護樹種名稱不可空白')
        calendar.setdefault(species_key(name), {'names': [], 'rules': []})['names'].append(name)
    seen = set()
    for row in rules:
        key = species_key(row.get('species_name', ''))
        months = row.get('months')
        if key not in calendar:
            raise ValueError('養護規則缺少對應樹種資料')
        if not isinstance(months, list) or any(type(month) is not int or month < 1 or month > 12 for month in months) or len(months) != len(set(months)):
            raise ValueError('養護月份必須為不重複的 1–12 月')
        level = row.get('evidence_level')
        if level not in {'general', 'reference', 'conflict', 'approved'}:
            raise ValueError('養護規則來源層級無效')
        if type(row.get('enabled')) is not bool or (row['enabled'] and (not months or level == 'conflict')):
            raise ValueError('有衝突或未填月份的規則不得啟用')
        urls = row.get('source_urls')
        if not isinstance(urls, list) or not urls or any(not isinstance(url, str) or urlparse(url).scheme != 'https' or not urlparse(url).hostname for url in urls):
            raise ValueError('養護規則需有 HTTPS 來源連結')
        if row.get('rule_type') not in {'general', 'flower', 'fruit', 'assessment'} or not row.get('event') or not row.get('action'):
            raise ValueError('養護規則類型或說明缺漏')
        fingerprint = (key, row['rule_type'], tuple(months), row['event'], tuple(urls))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        calendar[key]['rules'].append(row)
    for entry in calendar.values():
        if not any(rule['enabled'] and rule['rule_type'] == 'general' and set(rule['months']) == set(range(1, 13)) for rule in entry['rules']):
            raise ValueError('樹種缺少完整的全年通用觀察資料')
    return calendar


def load_care_calendar(environ=None, session=None):
    if session is None:
        with read_session() as client:
            return load_care_calendar(environ, client)
    profiles = load_rows(environ, session, table='tree_species_care_profiles',
                         select='id,species_name,expert_status,notes')
    rules = load_rows(environ, session, table='tree_species_care_rules',
                      select='id,species_name,months,rule_type,event,action,source_urls,source_note,evidence_level,enabled')
    return normalize_calendar(profiles, rules)


def month_rules(calendar, name, month, specific_only=True):
    return [row for row in calendar.get(species_key(name), {}).get('rules', [])
            if row['enabled'] and month in row['months']
            and (not specific_only or row['rule_type'] != 'general')]


def eligible_species(calendar, names, month):
    return [name for name in set(names) if month_rules(calendar, name, month)]

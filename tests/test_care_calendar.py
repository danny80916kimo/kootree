import json
from pathlib import Path

import pytest

from scripts.care_calendar import normalize_calendar, month_rules, eligible_species
from scripts.collect_care_sources import parse_months


def rule(name='臺灣欒樹', **extra):
    return dict({'species_name':name, 'months':list(range(1,13)), 'rule_type':'general',
                 'event':'全年例行觀察', 'action':'記錄樹木狀況', 'source_urls':['https://example.gov.tw/care'],
                 'source_note':'依管理計畫', 'evidence_level':'general', 'enabled':True}, **extra)


def calendar_rules():
    return normalize_calendar([{'species_name':'臺灣欒樹'}, {'species_name':'未確認樹種'}],
        [rule(),rule('未確認樹種'), rule(months=[8,9,10],rule_type='flower',event='花期觀察',evidence_level='reference'),
         rule(months=[10,11,12],rule_type='fruit',event='果期觀察',evidence_level='reference')])


def test_general_rules_do_not_make_every_species_a_month_specific_target():
    calendar=calendar_rules()
    assert eligible_species(calendar,['台灣欒樹','未確認樹種'],10) == ['台灣欒樹']
    assert len(month_rules(calendar,'臺灣欒樹',10)) == 2
    assert month_rules(calendar,'未確認樹種',10) == []
    assert len(month_rules(calendar,'未確認樹種',10,specific_only=False)) == 1


def test_disabled_conflicts_never_become_month_targets():
    calendar=normalize_calendar([{'species_name':'小葉欖仁'}], [rule('小葉欖仁'),
        rule('小葉欖仁',months=[],rule_type='flower',evidence_level='conflict',enabled=False)])
    assert month_rules(calendar,'小葉欖仁',10) == []
    with pytest.raises(ValueError,match='不得啟用'):
        normalize_calendar([{'species_name':'小葉欖仁'}], [rule('小葉欖仁'),
            rule('小葉欖仁',months=[10],rule_type='flower',evidence_level='conflict',enabled=True)])


@pytest.mark.parametrize('months',[[0],[13],[True],[1,1]])
def test_invalid_months_are_rejected(months):
    with pytest.raises(ValueError,match='1–12'):
        normalize_calendar([{'species_name':'臺灣欒樹'}],[rule(months=months)])


def test_incomplete_catalog_and_untrusted_source_scheme_are_rejected():
    with pytest.raises(ValueError,match='全年'):
        normalize_calendar([{'species_name':'臺灣欒樹'}],[])
    with pytest.raises(ValueError,match='HTTPS'):
        normalize_calendar([{'species_name':'臺灣欒樹'}],[rule(source_urls=['javascript:alert(1)'])])


def test_numeric_period_parser_wraps_year_without_guessing_seasons():
    assert parse_months('11月至翌年2月') == [1,2,11,12]
    assert parse_months('2~4月、8月') == [2,3,4,8]
    with pytest.raises(ValueError):
        parse_months('冬季')


def test_generated_sql_contains_every_seed_and_preserves_expert_edits():
    from scripts.build_care_calendar import ROOT
    sql=(ROOT/'supabase/seed_species_care_calendar.sql').read_text()
    payload=sql.split('$care_seed$')[1]
    seeds=json.loads(payload)
    assert len(seeds) >= 100
    assert all(seed['source_urls'] for seed in seeds)
    assert all(not seed['enabled'] for seed in seeds if seed['evidence_level']=='conflict')
    assert 'on conflict (id) do nothing' in sql
    assert 'update public.tree_locations' not in sql.lower()

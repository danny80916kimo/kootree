from uuid import uuid4
import pandas as pd

from scripts.audit_data_integrity import profile_trees, profile_reports, compare_official


def tree(code, **extra):
    return dict({'id':str(uuid4()), 'code':code, 'tree_type':'street','species_name':'榕樹',
                 'lat':25.03,'lng':121.5,'division_name':'大安區','address':None,'region':'測試路',
                 'height':5,'diameter':10}, **extra)


def test_zero_measurements_are_not_counted_as_complete_valid_measurements():
    stats, anomalies = profile_trees(pd.DataFrame([tree('1',height=0),tree('1',diameter=-1),tree('3',lat=0,lng=0)]))
    assert stats['fields']['height']['missing'] == 0
    assert stats['numeric']['height']['zero'] == 1
    assert stats['numeric']['diameter']['negative'] == 1
    assert stats['flags']['duplicate_code'] == 2
    assert stats['flags']['outside_taipei_review_box'] == 1
    assert len(anomalies) == 3


def test_protected_report_is_outside_dashboard_but_not_an_orphan():
    street, protected = tree('1'), tree('2',tree_type='protected')
    reports = pd.DataFrame([{'id':'report','tree_location_id':protected['id'],'type':'other',
                            'created_at':'2026-10-20T00:00:00Z','confirmed_at':None,'dismissed':False}])
    stats = profile_reports(reports,pd.DataFrame([street,protected]))
    assert stats['orphan_tree_references'] == 0
    assert stats['street_reports'] == 0
    assert stats['other_tree_reports'] == 1


def test_official_comparison_reports_both_set_differences_and_field_changes(tmp_path):
    cloud = pd.DataFrame([tree('common',height=6),tree('cloud-only')])
    official = pd.DataFrame([{'TreeID':code,'Dist':'大安區','Region':'測試路','TreeType':'榕樹',
                              'TreeHeight':'5','Diameter':'10','TWD97X':'303000','TWD97Y':'2770000'}
                             for code in ['common','official-only']])
    stats = compare_official(cloud,official,tmp_path)
    assert stats['codes_in_both'] == 1
    assert stats['supabase_only_codes'] == 1
    assert stats['official_only_codes'] == 1
    assert stats['field_mismatches']['height'] == 1

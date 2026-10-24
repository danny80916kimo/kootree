import importlib
import pandas as pd
import pytest

from scripts.supabase_data import normalize_reports, normalize_trees, attach_report_summary


def report(identifier, tree_id='t1', kind='病蟲害', confirmed=None, dismissed=False, created='2026-10-20T00:00:00Z'):
    return {'id':identifier, 'tree_location_id':tree_id, 'type':kind,
            'created_at':created, 'confirmed_at':confirmed, 'dismissed':dismissed}


def test_confirmation_is_not_case_closure_and_invalid_dates_are_unknown():
    rows = [report('1'), report('2', confirmed='2026-10-21T00:00:00Z'),
            report('3', dismissed=True), report('4', created='invalid'),
            report('5', created='2030-01-01T00:00:00Z')]
    data = normalize_reports(rows, now='2026-10-24T00:00:00Z')
    assert data['issue_status'].tolist() == ['待確認', '已確認', '已排除', '待確認', '待確認']
    assert data.iloc[0]['case_age_days'] == 4
    assert data.iloc[3:]['case_age_days'].isna().all()


@pytest.fixture
def dashboard(monkeypatch):
    import scripts.supabase_data as source
    trees = normalize_trees([{'tree_id':f't{i}', 'district':'大安區', 'road':'測試路',
                             'species':'榕樹', 'latitude':25.03, 'longitude':121.5} for i in (1,2)])
    reports = normalize_reports([report('1'), report('2', kind='落枝'),
                                report('3', 't2', confirmed='2026-10-21T00:00:00Z'),
                                report('4', 'protected-tree')], now='2026-10-24T00:00:00Z')
    monkeypatch.setattr(source, 'load_trees', lambda: trees)
    monkeypatch.setattr(source, 'load_reports', lambda: reports)
    app = importlib.import_module('dashboard_supabase')
    monkeypatch.setattr(app, 'trees', attach_report_summary(trees, reports))
    monkeypatch.setattr(app, 'reports', reports)
    monkeypatch.setattr(app, 'reports_ready', True)
    monkeypatch.setattr(app, 'ISSUE_TYPES', sorted(reports['issue_type'].unique()))
    return app


def render(app, issue='all', status='all', drill=None, district='all'):
    return app.update_dashboard(district,'all','all',issue,status,10,[],'species',drill or {})


def test_counts_reports_not_trees_and_excludes_out_of_scope(dashboard):
    result = render(dashboard)
    assert result[1] == '2'
    assert result[3] == '2'
    assert result[4] == '1500.00'  # Three reports / two trees; not three reporting trees.
    assert result[6] == '4.0'
    assert sum(result[11].data[0].x) == 3
    assert result[12].data[0].x[0] == 1500


def test_issue_filter_keeps_location_population_as_rate_denominator(dashboard):
    result = render(dashboard, issue='落枝')
    assert result[1] == '1'
    assert result[3] == '1'
    assert result[4] == '500.00'


def test_status_and_drill_must_match_the_same_report(dashboard):
    result = render(dashboard, status='已確認', drill={'type':'issue','issue_type':'落枝'})
    assert result[1] == '0'
    assert result[3] == '0'
    assert result[4] == '0.00'
    assert result[13] == []


def test_no_matching_reports_has_clear_empty_state_without_axes(dashboard):
    result = render(dashboard, issue='不存在')
    chart = result[11]
    assert not chart.data
    assert '目前篩選範圍無通報' in chart.layout.annotations[0].text
    assert chart.layout.xaxis.visible is False


def test_failed_report_connection_is_not_zero(dashboard, monkeypatch):
    monkeypatch.setattr(dashboard, 'reports_ready', False)
    monkeypatch.setattr(dashboard, 'reports', normalize_reports([]))
    result = render(dashboard)
    assert result[3] == '尚未連線'
    assert result[4] == '無法計算'
    assert '尚未連線' in result[11].layout.annotations[0].text


def test_demo_mode_isolated_from_real_data_and_prioritizes_reporting_trees(dashboard, monkeypatch):
    from scripts.supabase_data import normalize_demo_reports, attach_demo_risks
    demo = normalize_demo_reports([dict(report('demo-1', tree_id='t2'), is_simulated=True, risk_score=80, risk_level='高')])
    demo_trees = attach_demo_risks(attach_report_summary(dashboard.trees, demo), demo)
    monkeypatch.setattr(dashboard, 'demo_reports', demo)
    monkeypatch.setattr(dashboard, 'demo_trees', demo_trees)
    monkeypatch.setattr(dashboard, 'demo_ready', True)
    monkeypatch.setattr(dashboard, 'demo_message', '【模擬模式】')
    result = dashboard.update_dashboard('all','all','all','all','all',10,[],'species',{},'demo')
    assert result[3] == '1'
    assert result[4] == '500.00'
    assert result[5] == '1'
    assert result[13][0]['tree_id'] == 't2'
    assert result[13][0]['data_origin'] == '模擬通報／風險'
    assert render(dashboard)[3] == '2'  # real source remains unchanged
    badge, message, *_ = dashboard.update_source('demo')
    assert '模擬' in badge and '1 棵' in message


def test_demo_loader_rejects_unmarked_or_inconsistent_risks():
    from scripts.supabase_data import normalize_demo_reports
    row = dict(report('demo-1'), is_simulated=False, risk_score=80, risk_level='高')
    with pytest.raises(ValueError, match='標記'):
        normalize_demo_reports([row])
    with pytest.raises(ValueError, match='分級無效'):
        normalize_demo_reports([dict(row, is_simulated=True, risk_level='低')])


def test_table_and_map_use_official_code_but_clicks_keep_uuid(dashboard, monkeypatch):
    trees = dashboard.trees.copy()
    trees['tree_code'] = ['DA001','DA002']
    trees['height'] = [10.7,7.9]
    trees['diameter'] = [7.57,22]
    monkeypatch.setattr(dashboard, 'trees', trees)
    result = render(dashboard)
    row = result[13][0]
    assert row['tree_id'] == 't1'
    assert row['tree_code'] == 'DA001'
    assert row['height'] == 10.7
    assert row['diameter'] == 7.57
    custom = result[0].data[0].customdata
    assert custom[0][0] == 't1'
    assert custom[0][4] == 'DA001'
    details = dashboard.show_tree({'points':[{'customdata':custom[0]}]})
    assert details.children[0].children[1].children == 'DA001'


def test_road_card_dict_trigger_does_not_crash(dashboard, monkeypatch):
    from types import SimpleNamespace
    trigger={'type':'priority_road','district':'大安區','road':'測試路'}
    monkeypatch.setattr(dashboard, 'ctx', SimpleNamespace(triggered_id=trigger, inputs_list=[[],[{'id':trigger,'value':1}]]))
    result = dashboard.update_drill_filter(care_clicks=[],road_clicks=[1],issue_click=None,clear_clicks=0,
        district='all',road='all',species='all',issue='all',status='all',month=10,care_only=[],
        map_mode='species',data_source='demo')
    assert result['type'] == 'road'
    assert result['district'] == '大安區'


def test_month_care_counts_each_tree_once_and_restores_month_filter(dashboard,monkeypatch):
    from scripts.care_calendar import normalize_calendar
    common={'species_name':'榕樹','source_urls':['https://example.gov.tw/tree'],
            'source_note':'觀察參考','action':'記錄現地狀況','enabled':True}
    calendar=normalize_calendar([{'species_name':'榕樹'}],[
        dict(common,months=list(range(1,13)),rule_type='general',event='全年觀察',evidence_level='general'),
        dict(common,months=[10],rule_type='flower',event='花期觀察',evidence_level='reference'),
        dict(common,months=[10],rule_type='fruit',event='果期觀察',evidence_level='reference')])
    monkeypatch.setattr(dashboard,'CARE_CALENDAR',calendar)
    monkeypatch.setattr(dashboard,'CARE_READY',True)
    result=render(dashboard)
    assert result[8] == '2'  # two trees, not four event matches
    assert len(dashboard.filter_data('all','all','all','all','all',10,['care'])) == 2
    assert len(dashboard.filter_data('all','all','all','all','all',11,['care'])) == 0
    assert len(result[14]) >= 2


@pytest.mark.parametrize('trigger',[
    {'type':'care_card','species':'榕樹'},
    {'type':'priority_road','district':'大安區','road':'測試路'}])
def test_clicking_same_card_twice_restores_original_filters(dashboard,monkeypatch,trigger):
    from types import SimpleNamespace
    group=[{'id':trigger,'value':1}]
    monkeypatch.setattr(dashboard,'ctx',SimpleNamespace(triggered_id=trigger,
        inputs_list=[group,[]] if trigger['type']=='care_card' else [[],group]))
    arguments=dict(care_clicks=[1],road_clicks=[1],issue_click=None,clear_clicks=0,
        district='大安區',road='all',species='all',issue='all',status='all',month=10,care_only=[],
        map_mode='species',data_source='real')
    selected=dashboard.update_drill_filter(**arguments,current_filter={})
    assert selected
    restored=dashboard.update_drill_filter(**arguments,current_filter=selected)
    assert restored == {}
    original=dashboard.filter_data('大安區','all','all','all','all',10,[])
    assert dashboard.apply_drill_filter(original,restored).equals(original)
    # A third click after card regeneration must select again, even if n_clicks is 1.
    assert dashboard.update_drill_filter(**arguments,current_filter=restored) == selected


def test_recreated_zero_click_cards_do_not_clear_active_selection(dashboard,monkeypatch):
    from types import SimpleNamespace
    trigger={'type':'care_card','species':'榕樹'}
    monkeypatch.setattr(dashboard,'ctx',SimpleNamespace(triggered_id=trigger,
        inputs_list=[[{'id':trigger,'value':0}],[]]))
    current={'type':'species','species':'榕樹'}
    result=dashboard.update_drill_filter([],[],None,0,'all','all','all','all','all',10,[],'species','real',current)
    assert result is dashboard.no_update

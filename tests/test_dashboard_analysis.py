import pandas as pd
from scripts.dashboard_analysis import issue_chart, rate_chart, priority_chart, age_chart, report_history, history_chart
from scripts.supabase_data import normalize_reports, normalize_trees, attach_report_summary


def fixture_data():
    population=normalize_trees([dict(tree_id='a',tree_code='DA-001',district='大安區',road='測試路',species='榕樹',latitude=25.03,longitude=121.5),dict(tree_id='b',tree_code='DA-002',district='大安區',road='測試路',species='樟樹',latitude=25.04,longitude=121.51)])
    reports=normalize_reports([dict(id='r1',tree_location_id='a',type='落枝',created_at='2026-10-20T00:00:00Z',confirmed_at=None,dismissed=False),dict(id='r2',tree_location_id='a',type='落枝',created_at='2026-10-21T00:00:00Z',confirmed_at='2026-10-22T00:00:00Z',dismissed=False)],now='2026-10-24T00:00:00Z')
    return attach_report_summary(population,reports),reports


def test_multiple_reports_on_one_tree_are_counted_individually():
    population,reports=fixture_data()
    chart=issue_chart(reports)
    assert sum(sum(trace.x) for trace in chart.data)==2
    assert {trace.name:sum(trace.x) for trace in chart.data}=={'待確認':1,'已確認':1,'已排除':0}
    rate=rate_chart(population,reports)
    assert rate.data[0].x[0]==1000
    assert list(rate.data[0].customdata[0])==[2,2]


def test_priority_and_age_exclude_confirmed_reports_without_calling_them_closed():
    population,reports=fixture_data()
    chart=priority_chart(population,reports)
    assert list(chart.data[0].x)==[1]
    assert list(chart.data[0].y)==[0]
    ages=age_chart(reports)
    assert sum(ages.data[0].y)==1


def test_history_keeps_report_identity_and_does_not_invent_work_or_closure():
    population,reports=fixture_data()
    rows=report_history(population,reports)
    assert rows.id.tolist()==['r1','r2']
    assert rows.tree_code.tolist()==['DA-001','DA-001']
    assert not {'closed_date','team','work_action','inspection_date'}.intersection(rows.columns)
    chart=history_chart(rows)
    assert len(chart.data)==1 and sum(chart.data[0].y)==2
    assert chart.layout.xaxis.type=='category'
    assert chart.layout.yaxis.dtick is None
    assert '結案日期' in chart.layout.annotations[0].text


def test_map_points_keep_all_trees_and_limit_only_to_actual_viewport():
    from scripts.map_points import select_map_points
    population,_=fixture_data()
    assert len(select_map_points(pd.concat([population]*5001))[0])==10002
    view={'mapbox._derived':{'coordinates':[[121.49,25.02],[121.505,25.02],[121.505,25.035],[121.49,25.035]]}}
    visible,_=select_map_points(population,view)
    assert visible.tree_id.tolist()==['a']

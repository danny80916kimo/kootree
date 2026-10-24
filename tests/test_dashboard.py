from types import SimpleNamespace
import pytest
import app

@pytest.mark.parametrize('trigger,expected', [
    ({'type':'priority_road','district':'district-a','road':'road-a'}, 'road'),
    ({'type':'care_card','species':'species-a'}, 'species'),
    ('clear_drill', None),
    ('district_filter', None),
])
def test_card_drill_accepts_dictionary_ids(monkeypatch, trigger, expected):
    monkeypatch.setattr(app, 'ctx', SimpleNamespace(triggered_id=trigger))
    result = app.update_drill_filter([1], [1], None, 0, 'all', 'all', 'all', 'all', 'all', 10, [], 'species')
    if expected is None:
        assert result == {}
    else:
        assert result['type'] == expected
        if expected == 'road':
            assert result['district'] == 'district-a'
            assert result['road'] == 'road-a'
        else:
            assert result['species'] == 'species-a'

def test_care_species_matches_official_spelling():
    species = '\u53f0\u7063\u6b12\u6a39'
    assert not app.trees['species'].str.contains('\u81fa\u7063', regex=False).any()
    expected = app.trees[app.trees['species'] == species]
    assert len(expected) > 0
    result = app.update_dashboard('all','all','all','all','all',10,[],'species',{'type':'species','species':species})
    assert result[1] == f'{len(expected):,}'
    assert len(result[0].data) > 0


def test_empty_map_keeps_geographic_trace():
    result = app.update_dashboard('all','all','missing-species','all','all',10,[],'species',{})
    assert result[1] == '0'
    assert result[0].data[0].type == 'scattermapbox'
    assert any('目前篩選無資料' in str(annotation.text) for annotation in result[0].layout.annotations)

@pytest.mark.parametrize('trigger,click', [
    ({'type':'priority_road','district':'district-a','road':'road-a'}, None),
    ({'type':'care_card','species':'species-a'}, None),
    ('issue_chart', {'points':[{'y':'issue-a'}]}),
])
def test_same_card_toggles_off_and_different_card_switches(monkeypatch, trigger, click):
    monkeypatch.setattr(app, 'ctx', SimpleNamespace(triggered_id=trigger))
    args = ([1], [1], click, 0, 'all', 'all', 'all', 'all', 'all', 10, [], 'species')
    selected = app.update_drill_filter(*args, {})
    assert selected
    assert app.update_drill_filter(*args, selected) == {}
    assert app.update_drill_filter(*args, {'type':'other'}) == selected


def test_chart_totals_and_all_districts():
    from scripts.analytics_charts import inventory_chart, issue_chart, rate_chart, priority_chart, age_chart
    df=app.trees
    species=inventory_chart(df,'species')
    assert sum(species.data[0].values) == len(df)
    districts=inventory_chart(df,'district',df['district'].unique())
    assert len(districts.data[0].y) == 12
    assert sum(districts.data[0].x) == len(df)
    issues=issue_chart(df)
    assert sum(sum(trace.x) for trace in issues.data) == int(df['issue_type'].ne('無通報').sum())
    rates=rate_chart(df)
    assert len(rates.data[0].y) == 12
    assert rates.layout.shapes[0].x0 == pytest.approx(df['issue_type'].ne('無通報').mean()*1000)
    pending=df['issue_status'].isin(['待巡檢','處理中'])
    assert sum(age_chart(df).data[0].y) == int(pending.sum())
    roads=priority_chart(df)
    assert sum(roads.data[0].x) == int(pending.sum())
    for build in [issue_chart, rate_chart, priority_chart, age_chart]:
        build(df.iloc[:0]).to_json()


def test_priority_scatter_toggle(monkeypatch):
    monkeypatch.setattr(app,'ctx',SimpleNamespace(triggered_id='priority_chart'))
    args=([0],[0],None,0,'all','all','all','all','all',10,[],'species')
    click={'points':[{'customdata':['district-a','road-a',50]}]}
    result=app.update_drill_filter(*args,{},click)
    assert result['type']=='road'
    assert app.update_drill_filter(*args,result,click)=={}


def test_donut_matches_map_species_colors_after_filtering():
    result=app.update_dashboard('all','all','all','all','all',10,[],'species',{})
    donut=result[9].data[0]
    assert donut.type=='pie' and donut.hole==.60
    colors=dict(zip(donut.labels,donut.marker.colors))
    for trace in result[0].data:
        label='其他樹種（合計）' if trace.name=='其他樹種' else trace.name
        assert trace.marker.color==colors[label]
    species=next(iter(app.SPECIES_COLORS))
    filtered=app.update_dashboard('all','all',species,'all','all',10,[],'species',{})
    assert filtered[9].data[0].marker.colors[0]==app.SPECIES_COLORS[species]
    assert filtered[0].data[0].marker.color==app.SPECIES_COLORS[species]
    empty=app.update_dashboard('all','all','missing-species','all','all',10,[],'species',{})
    empty[9].to_json()


def test_care_shows_all_seasons_with_consistent_colors():
    result=app.update_dashboard('all','all','all','all','all',10,[],'care',{})
    traces=result[0].data
    assert traces[0].name=='其他樹木'
    assert 0 < traces[0].marker.opacity < .95
    for trace in traces[1:]:
        species=trace.name.split(' · ')[0]
        assert trace.marker.color==app.SPECIES_COLORS[species]
        assert trace.marker.opacity==.95
        assert '月' in trace.name
    assert len(traces)==5
    assert sum(len(t.lat) for t in traces)==len(app.trees.dropna(subset=['latitude','longitude']))
    march=app.update_dashboard('all','all','all','all','all',3,[],'care',{})
    assert [t.name for t in traces]==[t.name for t in march[0].data]


def test_small_focus_is_not_lost_in_sampling():
    df=app.trees
    background=df[~df['species'].isin(app.CARE_RULES)].head(9000)
    focus=df[df['species'].eq('木棉')].head(1)
    from unittest.mock import patch
    import pandas as pd
    with patch.object(app,'trees',pd.concat([background,focus])):
        result=app.update_dashboard('all','all','all','all','all',3,[],'care',{})
    assert sum(len(t.lat) for t in result[0].data if t.name.startswith('木棉'))==1


def test_species_slice_and_legend_share_filter(monkeypatch):
    args=([0],[0],None,0,'all','all','all','all','all',10,[],'species')
    species=app.trees['species'].value_counts().index[0]
    monkeypatch.setattr(app,'ctx',SimpleNamespace(triggered_id='species_chart',triggered=[{'prop_id':'species_chart.clickData'}]))
    selected=app.update_drill_filter(*args,{},None,{'points':[{'label':species}]},None,None)
    filtered=app.apply_drill_filter(app.trees,selected)
    assert filtered['species'].unique().tolist()==[species]
    dashboard=app.update_dashboard('all','all','all','all','all',10,[],'species',selected)
    assert dashboard[1]==f'{len(filtered):,}'
    assert sum(dashboard[9].data[0].values)==len(filtered)
    monkeypatch.setattr(app,'ctx',SimpleNamespace(triggered_id='species_chart',triggered=[{'prop_id':'species_chart.relayoutData'}]))
    labels=app.trees['species'].value_counts().head(10).index.tolist()+['其他樹種（合計）']
    figure={'data':[{'labels':labels}]}
    selected=app.update_drill_filter(*args,{},None,None,{'hiddenlabels':[s for s in labels if s!=species]},figure)
    assert app.apply_drill_filter(app.trees,selected)['species'].unique().tolist()==[species]


def test_issue_types_respect_species_eligibility():
    import pandas as pd
    names=['木棉','黑板樹','榕樹','樟樹','小葉欖仁']
    source=pd.DataFrame({'species':names*4000,'diameter_cm':40,'height_m':10,'issue_type':'old'})
    df=app.enrich_decision_demo_fields(source)
    assert set(df.loc[df['issue_type']=='種子飛絮','species']) <= {'木棉','黑板樹'}
    assert set(df.loc[df['issue_type']=='落果清理','species']) <= {'榕樹'}
    assert 'old' not in set(df['issue_type'])
    assert '落果飛絮' not in set(df['issue_type'])
    assert '疑似病蟲害' in set(df['issue_type'])
    pd.testing.assert_frame_equal(df, app.enrich_decision_demo_fields(source))


@pytest.mark.parametrize('chart',['district_chart','rate_chart'])
def test_district_chart_drills_all_data(monkeypatch,chart):
    selected_district=app.trees['district'].iloc[0]
    monkeypatch.setattr(app,'ctx',SimpleNamespace(triggered_id=chart))
    args=([0],[0],None,0,'all','all','all','all','all',10,[],'species')
    click={'points':[{'y':selected_district}]}
    extra={'district_click':click} if chart=='district_chart' else {'rate_click':click}
    drill=app.update_drill_filter(*args,**extra)
    expected=app.trees[app.trees['district']==selected_district]
    assert len(app.apply_drill_filter(app.trees,drill))==len(expected)
    result=app.update_dashboard('all','all','all','all','all',10,[],'species',drill)
    assert result[1]==f'{len(expected):,}'
    assert sum(result[9].data[0].values)==len(expected)
    assert all(row['district']==selected_district for row in result[13])
    assert app.update_drill_filter(*args,current_drill=drill,**extra)=={}


def test_district_dropdown_updates_dashboard_and_operations():
    selected=app.trees['district'].iloc[0]
    result=app.update_dashboard(selected,'all','all','all','all',10,[],'species',{})
    expected=app.trees[app.trees['district']==selected]
    assert result[1]==f'{len(expected):,}'
    rows=app.operation_rows('history',selected,'all','all','all','all',10,[],{})
    assert set(rows['district'])=={selected}


def test_repeated_chart_click_consumes_event_and_cancels(monkeypatch):
    district=app.trees['district'].iloc[0]
    monkeypatch.setattr(app,'ctx',SimpleNamespace(triggered_id='district_chart'))
    args=([0],[0],None,0,'all','all','all','all','all',10,[],'species')
    tail=(None,None,None,None,{'points':[{'y':district}]},None)
    first=app.update_drill_callback(*args,{},*tail)
    assert first[0]['district']==district
    assert first[1:]==(None,)*5
    second=app.update_drill_callback(*args,first[0],*tail)
    assert second[0]=={}
    assert second[1:]==(None,)*5

import app
from scripts.official_cases import records_from_geojson, filter_records, load_snapshot


def test_public_snapshot_retains_records_without_coordinates():
    snapshot = load_snapshot()
    records = records_from_geojson(snapshot)
    assert len(records) == len(snapshot['features']) > 0
    assert any(r['latitude'] is None for r in records)
    assert any(r['destinations'] for r in records)
    for record in records:
        assert record['url'].startswith('https://treesmatch.gov.taipei/')


def test_mentions_are_not_execution_status_or_counts():
    data = {'features': [{'id':1, 'geometry':None, 'properties':{
        'title':'澄清並非要移除樹木', 'content':'原地保留；未規劃移植。',
        'destinations':[{'label':'尚未定位的地點','latitude':None,'longitude':None}]}}]}
    records = records_from_geojson(data)
    assert records[0]['mentions_removal'] and records[0]['mentions_transplant']
    assert 'status' not in records[0] and 'tree_count' not in records[0]
    assert records[0]['latitude'] is None
    assert records[0]['destinations'][0]['latitude'] is None
    assert filter_records(records, 'removal', '原地保留') == records
    assert filter_records(records, 'all', '找不到的地點') == []


def test_case_endpoints_filter_and_keep_vendor_out_of_dash_bundle():
    client = app.server.test_client()
    rows = client.get('/official-tree-cases.json?topic=transplant').json['records']
    assert rows and all(r['mentions_transplant'] for r in rows)
    assert client.get('/official-tree-cases.json?q=not-a-real-case-zzzz').json['records'] == []
    page = client.get('/official-tree-map')
    assert page.status_code == 200
    assert b'tile.openstreetmap.org' in page.data
    assert b'API KEY REQUIRED' not in page.data
    assert client.get('/assets/vendor/leaflet.js').status_code == 200
    assert b'vendor/leaflet.js' not in client.get('/').data


def test_inventory_map_uses_keyless_muted_raster_style():
    result = app.update_dashboard('all','all','all','all','all',10,[],'species',{})
    style = result[0].layout.mapbox.style
    assert style['sources']['open-street-map']['tiles'][0].startswith('https://tile.openstreetmap.org/')
    raster = next(layer for layer in style['layers'] if layer['type'] == 'raster')
    assert raster['paint']['raster-saturation'] < 0
    assert raster['paint']['raster-opacity'] < .6


def test_official_overlay_is_additive_and_keeps_inventory_totals():
    args = ('all','all','all','all','all',10,[],'species',{})
    baseline = app.update_dashboard(*args)
    overlay = app.update_dashboard(*args, ['official'])
    assert baseline[1:9] == overlay[1:9]
    assert baseline[13] == overlay[13]
    assert len(overlay[0].data) > len(baseline[0].data)
    assert overlay[0].data[-1].uid.startswith('official-')
    assert len({t.name for t in overlay[0].data[len(baseline[0].data):]}) == len(overlay[0].data)-len(baseline[0].data)
    assert overlay[0].data[-1].customdata[0][0].startswith('official:')
    for before, after in zip(baseline[0].data, overlay[0].data):
        assert list(before.lat) == list(after.lat)


def test_single_map_layout_and_official_marker_reader(monkeypatch):
    from types import SimpleNamespace
    client = app.server.test_client()
    layout = client.get('/_dash-layout').get_data(as_text=True)
    assert 'map-workspace' in layout and 'official_case_detail' in layout
    assert 'official_case_map' not in layout  # No duplicate embedded map.
    monkeypatch.setattr(app, 'ctx', SimpleNamespace(triggered_id='tree_map'))
    tab, selected = app.select_map_record({'points':[{'customdata':['official:108']}]})
    assert (tab, selected) == ('official', '108')
    tab, _ = app.select_map_record({'points':[{'customdata':['BT0614021096']}]})
    assert tab == 'tree'


def test_shared_map_filters_official_rows_without_changing_inventory():
    args = ('all','all','all','all','all',10,[],'species',{})
    baseline = app.update_dashboard(*args)
    combined = app.update_dashboard(*args, ['official'], 'all', '美崙')
    assert combined[1:9] == baseline[1:9]
    official = combined[0].data[-1]
    assert official.uid.startswith('official-')
    assert all('美崙' in str(row) for row in official.customdata)

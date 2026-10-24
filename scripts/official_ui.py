"""Dash interface and local map endpoints for official public clarifications."""
from urllib.parse import urlencode, urlparse
from dash import html, dcc, dash_table, Input, Output, State, no_update
from flask import jsonify, request, send_file
from scripts.official_cases import ROOT, SOURCE, load_snapshot, records_from_geojson, filter_records


def safe_url(value):
    parsed = urlparse(value or '')
    return value if parsed.scheme == 'https' and parsed.hostname in (
        'treesmatch.gov.taipei', 'www-ws.gov.taipei') else None


def official_section():
    return html.Details([
        html.Summary('官方紀錄 · 搜尋與匯出', className='official-tools-title'),
        html.Div([html.Div('官方公開資訊', className='panel-title'),
                  html.A('小樹保衛站 ↗', href=SOURCE, target='_blank', rel='noopener noreferrer', className='source-link')], className='section-heading'),
        html.P('這裡收錄官方公開說明，並非全市逐株移除／移植清冊。分類僅依原文提及詞彙篩選，包含澄清、規劃與已完成事項；筆數不代表樹木株數。', className='help-text'),
        html.Div([
            html.Div([html.Label('說明主題', htmlFor='official_topic', className='field-label'),
                      dcc.Dropdown(id='official_topic', options=[{'label':'全部官方說明','value':'all'},
                          {'label':'原文提及移除／砍伐','value':'removal'}, {'label':'原文提及移植／遷移','value':'transplant'}],
                          value='all', clearable=False)], className='official-topic'),
            html.Div([html.Label('搜尋地點或內容', htmlFor='official_query', className='field-label'),
                      dcc.Input(id='official_query', placeholder='例如：大安森林公園、榕樹、移植', type='search', debounce=True)], className='official-search'),
        ], className='official-controls'),
        html.Div(id='official_summary', className='official-summary', role='status'),
        html.Div('公開說明清單 · 點選一列閱讀原文', className='filter-group-title official-list-title'),
        html.Button('匯出目前官方說明 CSV', id='official_export', className='export-btn'),
        dcc.Download(id='official_download'),
        dash_table.DataTable(id='official_cases_table', columns=[{'name':label,'id':key} for key,label in
                            [('published_at','發布日期'),('title','官方標題'),('location','地點'),('mapped','位置資料')]],
                            data=[], page_size=6, sort_action='native', cell_selectable=True,
                            style_table={'overflowX':'auto'},
                            style_cell={'textAlign':'left','padding':'12px','fontFamily':'inherit','fontSize':'12px',
                                        'backgroundColor':'#fffdf7','color':'#2e4534','whiteSpace':'normal','height':'auto','maxWidth':'420px'},
                            style_header={'backgroundColor':'#eeeadd','fontWeight':'bold'},
                            style_data_conditional=[{'if':{'row_index':'odd'},'backgroundColor':'#faf8f1'}]),
        html.P('座標為官方提供的概略位置；未提供座標者不在地圖標點。此區有獨立的主題與文字搜尋，不受上方行道樹與模擬案件篩選影響。', className='help-text official-location-note'),
    ], className='official-tools', id='official-cases')


def register_official(app):
    @app.server.get('/official-tree-map')
    def map_page():
        return send_file(ROOT / 'assets' / 'official-case-map.html', mimetype='text/html')

    @app.server.get('/official-tree-cases.json')
    def map_data():
        snapshot = load_snapshot()
        rows = filter_records(records_from_geojson(snapshot), request.args.get('topic', 'all'), request.args.get('q', ''))
        return jsonify(records=rows, updated_at=snapshot.get('updated_at'))

    @app.callback(Output('official_download','data'), Input('official_export','n_clicks'),
                  State('official_topic','value'), State('official_query','value'), prevent_initial_call=True)
    def export_official(n_clicks, topic, query):
        if not n_clicks:
            return no_update
        import pandas as pd
        rows = filter_records(records_from_geojson(load_snapshot()), topic, query)
        columns = ['id','title','published_at','publisher','location','latitude','longitude','content','url']
        return dcc.send_data_frame(pd.DataFrame(rows, columns=columns).to_csv,
                                   'official_tree_clarifications.csv', index=False, encoding='utf-8-sig')

    @app.callback(Output('official_summary','children'),
                  Output('official_case_select','options'), Output('official_case_select','value'),
                  Output('official_cases_table','data'),
                  Input('official_topic','value'), Input('official_query','value'), State('official_case_select','value'))
    def update_official(topic, query, selected):
        snapshot = load_snapshot()
        rows = filter_records(records_from_geojson(snapshot), topic, query)
        mapped = sum(r['latitude'] is not None and r['longitude'] is not None for r in rows)
        destinations = sum(len(r['destinations']) for r in rows)
        summary = [html.Strong(f'{len(rows)} 則公開說明'), html.Span(f'{mapped} 則可定位'),
                   html.Span(f'{len(rows)-mapped} 則未定位／全市資訊'), html.Span(f'{destinations} 筆目的地描述'),
                   html.Small(f"來源更新：{snapshot.get('updated_at') or '尚未下載'}｜本機快照，非即時同步")]
        options = [{'label':f"{r['published_at']}｜{r['title']}",'value':r['id']} for r in rows]
        value = selected if any(r['id'] == selected for r in rows) else (rows[0]['id'] if rows else None)
        table = [dict(id=r['id'], published_at=r['published_at'], title=r['title'], location=r['location'],
                      mapped='有概略座標' if r['latitude'] is not None else '未提供座標') for r in rows]
        return summary, options, value, table

    @app.callback(Output('official_case_detail','children'), Input('official_case_select','value'))
    def show_official(case_id):
        record = next((r for r in records_from_geojson(load_snapshot()) if r['id'] == case_id), None)
        if not record:
            return html.P('目前沒有符合條件的官方說明。', className='help-text')
        children = [html.H3(record['title']), html.P(f"{record['published_at']}｜{record['publisher']}",className='help-text'),
                    html.P('地點：'+record['location']), html.P(record['content'][:220]+('…' if len(record['content'])>220 else ''),className='official-excerpt'),
                    html.Details([html.Summary('閱讀完整官方說明'),html.P(record['content'],className='official-full-text')],className='official-full-details')]
        if record['destinations']:
            children += [html.H4('官方列出的移植目的地'), html.Ul([html.Li(d.get('label','') +
                ('（未提供座標）' if d.get('latitude') is None or d.get('longitude') is None else '（概略位置）')) for d in record['destinations']])]
        url = safe_url(record['url'])
        if url:
            children.append(html.A('前往官方原文 ↗',href=url,target='_blank',rel='noopener noreferrer',className='source-link'))
        return children

    @app.callback(Output('official_case_select','value', allow_duplicate=True), Input('official_cases_table','active_cell'),
                  State('official_cases_table','derived_viewport_data'), prevent_initial_call=True)
    def select_table(cell, rows):
        if not cell or not rows:
            return no_update
        return cell.get('row_id') or rows[cell['row']]['id']



def official_reader():
    return html.Div([
        html.Label('選擇官方說明，或點選地圖的官方標記', className='field-label'),
        dcc.Dropdown(id='official_case_select', options=[], placeholder='選擇一則說明', clearable=False),
        html.Div(id='official_case_detail', className='official-case-detail'),
    ], className='official-reader')

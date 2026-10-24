"""臺北市智慧行道樹管理 Dashboard | Dash MVP"""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Dash, dcc, html, Input, Output, State, callback, dash_table, ctx, no_update
from scripts.care_calendar import load_care_calendar, month_rules, eligible_species, species_key
from scripts.dashboard_charts import species_donut, district_distribution
from scripts.supabase_data import load_trees, empty_trees, load_reports, normalize_reports, attach_report_summary, load_demo_reports, normalize_demo_reports, attach_demo_risks

try:
    trees = load_trees()
    data_mode = 'Supabase 資料' if len(trees) else 'Supabase：無可讀取資料（請確認資料表及 RLS 權限）'
except ValueError as error:
    trees = empty_trees()
    data_mode = f'Supabase 尚未載入：{error}'

reports = normalize_reports([])
reports_ready = False
report_message = '樹木資料尚未載入'
if len(trees):
    try:
        reports = load_reports()
        trees = attach_report_summary(trees, reports)
        reports_ready = True
        report_message = f'通報已連線：全庫 {len(reports):,} 筆；圖表僅計算目前行道樹範圍（含已排除通報）'
    except ValueError as error:
        report_message = f'通報載入失敗：{error}'

demo_reports = normalize_demo_reports([])
demo_trees = empty_trees()
demo_ready = False
demo_message = '模擬通報尚未載入'
if len(trees):
    try:
        demo_reports = load_demo_reports()
        demo_trees = attach_demo_risks(attach_report_summary(trees, demo_reports), demo_reports)
        demo_ready = True
        demo_message = f'【模擬模式】通報與風險均為虛構展示資料，共 {len(demo_reports):,} 筆；樹籍來自真實行道樹。不可作為實際養護指令。'
    except ValueError as error:
        demo_message = f'模擬資料尚不可用：{error}'
INITIAL_MODE = 'demo' if demo_ready and len(demo_reports) else 'real'


def mode_data(data_source='real'):
    if data_source == 'demo':
        return demo_trees, demo_reports, demo_ready, demo_message
    return trees, reports, reports_ready, report_message


CARE_CALENDAR = {}
care_load_message = '養護月份資料尚未載入'
if len(trees):
    try:
        CARE_CALENDAR = load_care_calendar()
        care_load_message = '養護資料已連線；月份供觀察與專業評估參考'
    except ValueError:
        care_load_message = '養護月份資料尚未載入，請由資料管理者確認匯入與讀取權限。'
CARE_READY = bool(CARE_CALENDAR)
ISSUE_TYPES = sorted(reports['issue_type'].unique())
ISSUE_STATUS = ['待確認','已確認','已排除']
MONTH_OPTIONS = [{'label':f'{i} 月', 'value':i} for i in range(1,13)]
current_month = pd.Timestamp.now(tz='Asia/Taipei').month
SPECIES_PALETTE = ['#0b7556','#a56b34','#5c8a3e','#d66d43','#6379b4','#8e63a2','#42a6a0','#ca9a45']
OTHER_SPECIES_COLOR = '#8a948e'

external_stylesheets = ['https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&family=Noto+Serif+TC:wght@500;600&display=swap']
app = Dash(__name__, assets_folder='supabase_assets', title='做伙顧樹 KooTree｜城市樹木資訊與公民照護平台', external_stylesheets=external_stylesheets)
server = app.server

def dropdown(id, label, options, value='all'):
    return html.Div([html.Label(label, className='field-label'), dcc.Dropdown(id=id,options=options,value=value,clearable=False)],className='field')

def opts(series):
    return [{'label':'全部','value':'all'}]+[{'label':str(x),'value':str(x)} for x in sorted(series.dropna().astype(str).unique())]

def metric(title, value_id, icon, tone=''):
    icon_name = {'total_trees':'tree', 'open_cases':'report', 'high_risk_count':'risk', 'case_rate':'rate', 'district_count':'place', 'avg_case_age':'time', 'species_count':'leaf', 'care_count':'season'}[value_id]
    return html.Div([html.Div(html.Span(className='botanical-icon', style={'maskImage':f'url({app.get_asset_url("branding/icons/" + icon_name + ".svg")})'}, **{'aria-hidden':'true'}),className='metric-icon'),html.Div(title,className='metric-label'),html.Div(id=value_id,className='metric-value')],className=f'metric {tone}'.strip())

app.layout = html.Div([
    dcc.Store(id='drill_filter', data={}),
    html.Header([
        html.Div([
            html.Img(src=app.get_asset_url('branding/kootree-logo.png'), alt='KooTree 樹冠與家園標誌', width=80, height=72),
            html.Div([html.H1('做伙顧樹'), html.Div('KooTree', className='c-brand-english'), html.P('做伙顧樹，讓樹安好。')]),
        ], className='c-brand'),
        html.Div(className='c-scene', **{'aria-hidden':'true'}),
        html.Div([html.Span('●',className='online' if len(trees) else ''),html.Span(data_mode, id='source_badge')],className='data-badge')
    ],className='masthead-c', **{'aria-label':'做伙顧樹 KooTree｜做伙顧樹，讓樹安好。'}),
    html.Div([
        html.Aside([
            html.Div([html.Div('資料篩選',className='panel-title'),html.P('先選位置，再依樹種、案件或圖層縮小範圍。',className='sidebar-lead')],className='sidebar-head'),
            html.Div([
                html.Div('資料模式',className='filter-group-title'),
                dcc.RadioItems(id='data_source', options=[{'label':'真實通報','value':'real'}, {'label':'模擬通報（展示用）','value':'demo'}], value=INITIAL_MODE, className='radio-items'),
            ],className='filter-block'),
            html.Div([
                html.Div('位置範圍',className='filter-group-title'),
                dropdown('district_filter','行政區',opts(trees['district'])),
                dropdown('road_filter','路段',[{'label':'全部','value':'all'}]),
            ],className='filter-block'),
            html.Div([
                html.Div('資料條件',className='filter-group-title'),
                dropdown('species_filter','樹種',opts(trees['species'])),
                dropdown('issue_filter','通報類型',opts(mode_data(INITIAL_MODE)[1]['issue_type'])),
                dropdown('status_filter','通報確認狀態',opts(mode_data(INITIAL_MODE)[1]['issue_status'])),
                dropdown('month_filter','養護觀察月份', MONTH_OPTIONS,current_month),
                dcc.Checklist(id='care_only',options=[{'label':'只看本月有樹種專屬參考','value':'care','disabled':not CARE_READY}],value=[],className='check-option'),
            ],className='filter-block'),
            html.Div([
                html.Div('資料說明',className='filter-group-title'),
                html.P('僅顯示 Supabase 提供的資料；缺少的案件、風險與養護資訊標示為未提供。',className='help-text'),
                html.A('Supabase 專案 ↗',href='https://supabase.com/dashboard/project/pxglzzlihfhdjulegxag',target='_blank',className='source-link'),
            ],className='filter-block subtle-block'),
        ],className='sidebar'),
        html.Main([
            html.Nav([html.A('行道樹總覽',href='#tree-overview'),html.A('樹木分布地圖',href='#map-workspace'),html.A('統計與明細',href='#summary-charts')],className='data-navigation', **{'aria-label':'資料區塊導覽'}),
            html.Div([
                metric('符合條件樹木','total_trees','樹','primary'),
                metric('待確認通報','open_cases','件','warning'),
                metric('高風險（已評估樹木）','high_risk_count','警','danger'),
                metric('每千棵通報','case_rate','率','primary'),
                metric('涵蓋行政區','district_count','區'),
                metric('待確認通報平均天數','avg_case_age','天'),
                metric('樹種數量','species_count','種'),
                metric('當月物候／養護參考','care_count','期')
            ],id='tree-overview',className='metric-grid metric-grid-wide'),
            html.Div([
                html.Section([html.Div([html.Div('樹木分布地圖',className='panel-title'),html.Span('可點選地圖樹木標記',className='note')],className='section-heading'),html.Div([                dcc.RadioItems(id='map_mode', options=[{'label':'樹種分布','value':'species'},{'label':'養護月份參考','value':'care','disabled':not CARE_READY},{'label':'通報熱點','value':'issue'},{'label':'風險分級','value':'risk'}],value='species',className='map-layer-options'),
                html.Button('清除圖卡篩選',id='clear_drill',className='clear-drill-btn map-clear-btn'),
],className='map-toolbar'),html.Div(id='drill_label',className='drill-label muted'),dcc.Graph(id='tree_map',config={'displayModeBar':True,'scrollZoom':True},style={'height':'540px'})],className='surface map-panel'),
                html.Section([html.Div('樹木資訊',className='panel-title'),html.Div('請點選地圖標記，查看該棵樹的資料。',id='tree_details',className='tree-detail'),html.Div('當月養護觀察',className='panel-title section-gap'),html.Div(id='care_list'),html.Div('待確認通報路段',className='panel-title section-gap'),html.Div(id='priority_roads')],className='surface details-panel')
            ],id='map-workspace',className='main-grid'),
            html.P(mode_data(INITIAL_MODE)[3], id='source_message', className='help-text'),
            html.Div([
                html.Section([html.Div('樹種占比 · TOP 10 與其他',className='panel-title'),dcc.Graph(id='species_chart',config={'displayModeBar':False},responsive=True,style={'height':'520px'})],className='surface summary-chart-panel'),
                html.Section([html.Div('行政區樹木數量 · 完整 12 區',className='panel-title'),dcc.Graph(id='district_chart',config={'displayModeBar':False},responsive=True,style={'height':'520px'})],className='surface summary-chart-panel'),
                html.Section([html.Div('問題通報類型',className='panel-title'),dcc.Graph(id='issue_chart',config={'displayModeBar':False})],className='surface'),
                html.Section([html.Div('行政區每千棵通報率',className='panel-title'),dcc.Graph(id='rate_chart',config={'displayModeBar':False})],className='surface')
            ],id='summary-charts',className='chart-grid'),
            html.Section([html.Div([html.Div('篩選結果明細',className='panel-title'),html.Button('匯出篩選 CSV',id='export_button',className='export-btn')],className='section-heading'),
                dash_table.DataTable(id='tree_table',columns=[{'name':label,'id':col} for col,label in [('tree_code','樹木編號'),('data_origin','資料性質'),('district','行政區'),('road','路段'),('species','樹種'),('issue_type','通報類型'),('issue_status','通報確認狀態'),('risk_level','風險'),('risk_score','分數'),('diameter','胸徑（來源值）'),('height','樹高（來源值）'),('survey_date','調查日期')]],page_size=12,sort_action='native',style_table={'overflowX':'auto'},style_cell={'fontFamily':'Noto Sans TC, sans-serif','textAlign':'left','padding':'11px','border':'none','fontSize':'12px'},style_header={'backgroundColor':'#f2f6f4','fontWeight':'bold','color':'#455b52'},style_data_conditional=[{'if':{'row_index':'odd'},'backgroundColor':'#fafcfb'}]),dcc.Download(id='csv_download')],className='surface table-panel'),
            html.Footer([html.Div('做伙顧樹 KooTree · 做伙顧樹，讓樹安好。',className='footer-brand'),html.Div('資料來源：Supabase｜啟動時載入資料；更新後請重新啟動。未提供的欄位不產生示範推估。')],className='footer')
        ],className='content')
    ],className='layout')
],className='page')

@app.callback(Output('source_badge','children'),Output('source_message','children'),
          Output('issue_filter','options'),Output('issue_filter','value'),
          Output('status_filter','options'),Output('status_filter','value'),
          Input('data_source','value'))
def update_source(data_source):
    selected_trees, selected_reports, ready, message = mode_data(data_source)
    if data_source == 'demo' and ready:
        evaluated = selected_trees['risk_score'].notna().sum()
        message += f' 模擬評估涵蓋 {evaluated:,} 棵，其餘樹木沒有風險評估。'
    badge = 'Supabase · 模擬資料（展示用）' if data_source == 'demo' else data_mode
    return badge, message, opts(selected_reports['issue_type']), 'all', opts(selected_reports['issue_status']), 'all'


@app.callback(Output('road_filter','options'),Output('road_filter','value'),Input('district_filter','value'))
def update_roads(district):
    df=trees if district=='all' else trees[trees['district']==district]
    return opts(df['road']), 'all'

@app.callback(Output('drill_filter','data'),Input({'type':'care_card','species':ALL},'n_clicks'),Input({'type':'priority_road','district':ALL,'road':ALL},'n_clicks'),Input('issue_chart','clickData'),Input('clear_drill','n_clicks'),Input('district_filter','value'),Input('road_filter','value'),Input('species_filter','value'),Input('issue_filter','value'),Input('status_filter','value'),Input('month_filter','value'),Input('care_only','value'),Input('map_mode','value'),Input('data_source','value'),State('drill_filter','data'),prevent_initial_call=True)
def update_drill_filter(care_clicks,road_clicks,issue_click,clear_clicks,district,road,species,issue,status,month,care_only,map_mode,data_source,current_filter=None):
    trigger = ctx.triggered_id
    if trigger == 'clear_drill':
        return {}
    if isinstance(trigger, str) and trigger in {'district_filter','road_filter','species_filter','issue_filter','status_filter','month_filter','care_only','map_mode','data_source'}:
        return {}
    if isinstance(trigger, dict):
        # Dashboard redraws recreate cards at n_clicks=0. These events must not
        # toggle the selection or depend on click-count parity.
        inputs = [item for group in ctx.inputs_list[:2] for item in group]
        if not any(item.get('id') == trigger and item.get('value') for item in inputs):
            return no_update
    current_filter = current_filter or {}
    if isinstance(trigger, dict) and trigger.get('type') == 'care_card':
        species = trigger.get('species')
        if current_filter.get('type') == 'species' and current_filter.get('species') == species:
            return {}
        return {'type':'species','species':species,'label':f'物候關注樹種：{species}'}
    if isinstance(trigger, dict) and trigger.get('type') == 'priority_road':
        district = trigger.get('district')
        road = trigger.get('road')
        if current_filter.get('type') == 'road' and current_filter.get('district') == district and current_filter.get('road') == road:
            return {}
        return {'type':'road','district':district,'road':road,'label':f'優先巡檢路段：{district} · {road}'}
    if trigger == 'issue_chart' and issue_click:
        issue_type = issue_click['points'][0].get('y')
        if issue_type:
            return {'type':'issue','issue_type':issue_type,'label':f'通報類型：{issue_type}'}
    return no_update

@app.callback(Output('drill_label','children'),Output('drill_label','className'),Input('drill_filter','data'))
def render_drill_label(drill_filter):
    if not drill_filter:
        return '未套用圖卡篩選；可點選右側卡片或下方問題通報長條圖進行鑽取。','drill-label muted'
    hint = '（再點同張卡片取消）' if drill_filter.get('type') in {'species','road'} else ''
    return f"目前鑽取：{drill_filter.get('label','自訂條件')}{hint}",'drill-label active'

def filter_data(district,road,species,issue,status,month,care_only,data_source='real'):
    selected_trees, selected_reports, _, _ = mode_data(data_source)
    df=selected_trees
    for col,value in [('district',district),('road',road),('species',species)]:
        if value != 'all':df=df[df[col]==value]
    if issue != 'all' or status != 'all':
        matching = filter_reports(selected_reports, issue, status)
        df = df[df['tree_id'].isin(matching['tree_id'])]
    if 'care' in (care_only or []):
        allowed=eligible_species(CARE_CALENDAR, df['species'], month)
        df=df[df['species'].isin(allowed)]
    return df

def apply_drill_filter(df, drill_filter, data_source='real'):
    if not drill_filter:
        return df
    kind = drill_filter.get('type')
    if kind == 'species':
        return df[df['species'] == drill_filter.get('species')]
    if kind == 'road':
        return df[(df['district'] == drill_filter.get('district')) & (df['road'] == drill_filter.get('road'))]
    if kind == 'issue':
        selected_reports = mode_data(data_source)[1]
        matching = selected_reports[selected_reports['issue_type'].eq(drill_filter.get('issue_type'))]
        return df[df['tree_id'].isin(matching['tree_id'])]
    return df

def filter_reports(source, issue='all', status='all', drill_filter=None):
    selected = source
    if issue != 'all':
        selected = selected[selected['issue_type'].eq(issue)]
    if status != 'all':
        selected = selected[selected['issue_status'].eq(status)]
    if drill_filter and drill_filter.get('type') == 'issue':
        selected = selected[selected['issue_type'].eq(drill_filter.get('issue_type'))]
    return selected


def report_empty_figure(message, title):
    chart = go.Figure()
    chart.update_layout(height=310, margin={'l':25,'r':25,'t':20,'b':35},
                        paper_bgcolor='white', plot_bgcolor='white',
                        xaxis={'visible':False}, yaxis={'visible':False})
    chart.add_annotation(text=message, x=.5, y=.5, xref='paper', yref='paper', showarrow=False)
    return chart


def render_care_items(df, month):
    if not CARE_READY:
        return [html.P(care_load_message, className='help-text')]
    if df.empty:
        return [html.P('目前篩選範圍沒有樹木。', className='help-text')]
    names = df['species'].value_counts()
    result = [html.P('花果期及歷史月曆僅供參考，修剪須現地專業評估。', className='help-text')]
    general_actions, general_sources = [], []
    for name in names.index:
        for row in month_rules(CARE_CALENDAR, name, month, specific_only=False):
            if row['rule_type'] == 'general':
                general_actions.append(row['action'])
                general_sources.extend(row['source_urls'])
    if general_actions:
        result.append(html.Details([html.Summary('全年例行觀察'),
            *[html.P(action, className='help-text') for action in dict.fromkeys(general_actions)],
            *[html.A('巡查參考依據 ↗',href=url,target='_blank',rel='noopener noreferrer',className='source-link') for url in dict.fromkeys(general_sources)]]))
    cards, pending, uncatalogued, conflicts = [], 0, 0, 0
    for name, count in names.items():
        profile = CARE_CALENDAR.get(species_key(name))
        if not profile:
            uncatalogued += 1
            continue
        rules = month_rules(CARE_CALENDAR, name, month)
        has_specific = any(row['enabled'] and row['rule_type'] != 'general' for row in profile['rules'])
        pending += not has_specific
        conflicts += any(row['evidence_level'] == 'conflict' for row in profile['rules'])
        if not rules:
            continue
        events = ' · '.join(dict.fromkeys(row['event'] for row in rules))
        actions = ' '.join(dict.fromkeys(row['action'] for row in rules))
        sources = list(dict.fromkeys(url for row in rules for url in row['source_urls']))
        cards.append(html.Div([
            html.Button([html.B(f'{name} · {count:,} 棵'), html.Small(events), html.P(actions)],
                        id={'type':'care_card','species':name}, n_clicks=0,
                        className='care-item card-action', title=f'篩選 {name}；再點一次取消'),
            html.Details([html.Summary('參考依據／待現地確認'),
                          *[html.P(row['source_note'], className='help-text') for row in rules],
                          *[html.A(f'來源 {index+1} ↗',href=url,target='_blank',rel='noopener noreferrer',className='source-link') for index,url in enumerate(sources)]], className='help-text')
        ]))
    if cards:
        result.extend(cards[:6])
        if len(cards) > 6:
            result.append(html.Details([html.Summary(f'其他 {len(cards)-6} 種本月參考'), *cards[6:]]))
    else:
        result.append(html.P(f'{month} 月目前沒有符合篩選條件的樹種專屬月份參考；持續例行觀察。',className='help-text'))
    if pending:
        result.append(html.P(f'目前範圍有 {pending} 個樹種名稱僅有全年通用資料，專屬月份待確認。',className='help-text'))
    if conflicts:
        result.append(html.P(f'{conflicts} 個樹種存在月份來源差異；衝突規則未啟用。',className='help-text'))
    if uncatalogued:
        result.append(html.P(f'{uncatalogued} 個樹種名稱尚未建檔，請資料管理者補登。',className='help-text'))
    return result


@app.callback(Output('tree_map','figure'),Output('total_trees','children'),Output('district_count','children'),Output('open_cases','children'),Output('case_rate','children'),Output('high_risk_count','children'),Output('avg_case_age','children'),Output('species_count','children'),Output('care_count','children'),Output('species_chart','figure'),Output('district_chart','figure'),Output('issue_chart','figure'),Output('rate_chart','figure'),Output('tree_table','data'),Output('care_list','children'),Output('priority_roads','children'),Input('district_filter','value'),Input('road_filter','value'),Input('species_filter','value'),Input('issue_filter','value'),Input('status_filter','value'),Input('month_filter','value'),Input('care_only','value'),Input('map_mode','value'),Input('drill_filter','data'),Input('data_source','value'))
def update_dashboard(district,road,species,issue,status,month,care_only,map_mode,drill_filter,data_source='real'):
    _, reports, reports_ready, _ = mode_data(data_source)
    df=apply_drill_filter(filter_data(district,road,species,issue,status,month,care_only,data_source),drill_filter,data_source)
    # The denominator is the location/species population before report filters.
    population = filter_data(district,road,species,'all','all',month,care_only,data_source)
    spatial_drill = drill_filter if (drill_filter or {}).get('type') != 'issue' else None
    population = apply_drill_filter(population, spatial_drill, data_source)
    issue_df = filter_reports(reports, issue, status, drill_filter)
    issue_df = issue_df[issue_df['tree_id'].isin(df['tree_id'])]
    if issue != 'all' or status != 'all' or (drill_filter or {}).get('type') == 'issue':
        df = df[df['tree_id'].isin(issue_df['tree_id'])]
    open_df = issue_df[issue_df['issue_status'].eq('待確認')]
    open_df = open_df.merge(df[['tree_id','district','road','risk_level']], on='tree_id', how='left')
    missing_report_text = '通報尚未連線，請查看載入狀態'
    if reports_ready:
        missing_report_text = f'目前篩選範圍無通報（全庫 {len(reports):,} 筆）'
    care_species = set(eligible_species(CARE_CALENDAR, df['species'], month))
    count_care = int(df['species'].isin(care_species).sum())
    top_species=df['species'].value_counts().head(8).index.tolist()
    color_map={name:color for name,color in zip(top_species,SPECIES_PALETTE)}
    fig=go.Figure()
    # For responsiveness, map draws at most 8k points but all KPIs and tables use complete filtered data.
    map_df = df[df['tree_id'].isin(issue_df['tree_id'])] if map_mode == 'issue' else df
    plotted=map_df if len(map_df)<=8000 else map_df.sample(8000,random_state=42)
    if len(plotted):
        if map_mode=='care':
            plotted=plotted.copy()
            plotted['map_group']=plotted['species'].apply(lambda s:'本月關注' if s in care_species else '一般樹木')
            groups=['本月關注','一般樹木']
            colors={'本月關注':'#f09b3d','一般樹木':'#2d8a68'}
        elif map_mode=='issue':
            plotted=plotted.copy()
            plotted['map_group']=plotted['issue_type']
            groups=sorted(set(plotted['map_group']))
            colors={'落枝枯枝':'#b9473f','側枝遮擋':'#cf7c2b','根系隆起':'#8c6f34','病蟲害':'#8b579c','落果飛絮':'#d49b3b','樹木傾斜':'#7c3f33','無通報':'#6b8f80'}
        elif map_mode=='risk':
            plotted=plotted.copy()
            plotted['map_group']=plotted['risk_level']
            groups=['高','中','低','未提供']
            colors={'高':'#bd3f37','中':'#d99132','低':'#287c5d','未提供':'#8a948e'}
        else:
            plotted=plotted.copy()
            plotted['map_group']=plotted['species'].apply(lambda s:s if s in top_species else '其他樹種')
            groups=[name for name in top_species if name in set(plotted['map_group'])]
            if '其他樹種' in set(plotted['map_group']):
                groups.append('其他樹種')
            colors={**color_map,'其他樹種':OTHER_SPECIES_COLOR}
        for group in groups:
            part=plotted[plotted['map_group']==group]
            if part.empty:continue
            custom=part[['tree_id','district','road','species','tree_code']].fillna('').astype(str).to_numpy()
            fig.add_trace(go.Scattermapbox(lat=part['latitude'],lon=part['longitude'],mode='markers',name=group,
                marker={'size':9 if group in ['本月關注','高'] else 7,'color':colors.get(group,'#438e6e'),'opacity':.82},customdata=custom,
                hovertemplate='<b>%{customdata[3]}</b><br>%{customdata[1]} · %{customdata[2]}<br>樹木編號: %{customdata[4]}<extra></extra>'))
    fig.update_layout(mapbox={'style':'open-street-map','center':{'lat':float(df['latitude'].median()) if len(df) else 25.05,'lon':float(df['longitude'].median()) if len(df) else 121.54},'zoom':12 if district=='all' else 13.3},margin={'l':0,'r':0,'t':0,'b':0},height=540,legend={'orientation':'h','y':0.99,'x':.01,'bgcolor':'rgba(255,255,255,.88)','bordercolor':'#dce8e2','borderwidth':1,'font':{'size':11},'itemwidth':42},uirevision=f'{district}-{road}')
    def issue_fig():
        if not reports_ready or issue_df.empty:
            return report_empty_figure(missing_report_text, '件數')
        counts=issue_df['issue_type'].value_counts().sort_values()
        chart=go.Figure(go.Bar(x=counts.values,y=counts.index,orientation='h',marker_color='#b65f4a',hovertemplate='%{y}: %{x:,} 件<extra></extra>'))
        chart.update_layout(height=310,margin={'l':85,'r':15,'t':15,'b':35},paper_bgcolor='white',plot_bgcolor='white',font={'family':'Noto Sans TC'},xaxis={'gridcolor':'#eef1ee','title':'通報筆數'},yaxis={'title':''})
        return chart
    def rate_fig():
        if not reports_ready or population.empty:
            return report_empty_figure(missing_report_text if not reports_ready else '目前篩選範圍無樹木，無法計算比率', '件 / 千棵')
        if issue_df.empty:
            return report_empty_figure(missing_report_text + '；通報率為 0', '件 / 千棵')
        base=population.groupby('district').size()
        cases=issue_df.merge(population[['tree_id','district']], on='tree_id').groupby('district').size()
        rate=(cases.reindex(base.index, fill_value=0)/base*1000).sort_values()
        chart=go.Figure(go.Bar(x=rate.values,y=rate.index,orientation='h',marker_color='#5f789d',hovertemplate='%{y}: %{x:.2f} 件 / 千棵<extra></extra>'))
        chart.update_layout(height=310,margin={'l':85,'r':15,'t':15,'b':35},paper_bgcolor='white',plot_bgcolor='white',font={'family':'Noto Sans TC'},xaxis={'gridcolor':'#eef1ee','title':'件 / 千棵'},yaxis={'title':''})
        return chart
    care_items=render_care_items(df, month)
    road_summary=open_df.groupby(['district','road']).agg(cases=('id','size'),avg_age=('case_age_days','mean')).reset_index()
    road_summary=road_summary.sort_values(['cases','avg_age'],ascending=False).head(5)
    if road_summary.empty:
        priority=[html.P('目前範圍沒有待確認通報。' if reports_ready else '通報尚未連線。',className='help-text')]
    else:
        priority=[html.Button([html.B(f"{row.district} · {row.road}"),html.Small(f"待確認 {int(row.cases)} 件")],id={'type':'priority_road','district':row.district,'road':row.road},n_clicks=0,className='priority-item card-action',title=f'篩選 {row.district} {row.road}；再點一次取消') for row in road_summary.itertuples()]
    df = df.copy()
    df['data_origin'] = '模擬通報／風險' if data_source == 'demo' else '真實資料'
    if 'report_count' in df:
        df = df.sort_values('report_count', ascending=False, kind='stable')
    display_columns=['tree_id','tree_code','data_origin','district','road','species','issue_type','issue_status','risk_level','risk_score','diameter','height','survey_date']
    for col in display_columns:
        if col not in df:df=df.assign(**{col:''})
    rate_value=(len(issue_df)/len(population)*1000) if len(population) else None
    has_risk = len(df) > 0 and (df['risk_level'].ne('未提供').any() if data_source == 'demo' else df['risk_level'].ne('未提供').all())
    has_age = reports_ready and len(open_df) > 0 and open_df['case_age_days'].notna().all()
    avg_age=open_df['case_age_days'].mean() if has_age else None
    return fig,f'{len(df):,}',str(df['district'].nunique()),f'{len(open_df):,}' if reports_ready else '尚未連線',f'{rate_value:.2f}' if reports_ready and rate_value is not None else '無法計算',f"{int((df['risk_level']=='高').sum()):,}" if has_risk else '缺少評估',f'{avg_age:.1f}' if has_age else ('無待確認' if reports_ready and open_df.empty else '缺少日期'),str(df['species'].nunique()),f'{count_care:,}' if CARE_READY else '尚未載入',species_donut(df),district_distribution(df),issue_fig(),rate_fig(),df[display_columns].head(1000).astype(object).where(pd.notna(df[display_columns].head(1000)), '未提供').to_dict('records'),care_items,priority

@app.callback(Output('tree_details','children'),Input('tree_map','clickData'),Input('data_source','value'))
def show_tree(click_data,data_source='real'):
    trees = mode_data(data_source)[0]
    if not click_data:return '請點選地圖標記，查看該棵樹的資料。'
    selected_id=str(click_data['points'][0].get('customdata',[''])[0])
    found=trees[trees['tree_id'].astype(str)==selected_id]
    if found.empty:return '找不到所選樹木資料。'
    row=found.iloc[0]
    def text_value(key,suffix=''):
        v=row.get(key,'')
        return '未記載' if pd.isna(v) or str(v)=='' else f'{v}{suffix}'
    fields=[('樹木編號',text_value('tree_code')),('行政區',text_value('district')),('路段',text_value('road')),('樹種',text_value('species')),('通報類型',text_value('issue_type')),('通報確認狀態',text_value('issue_status')),('風險分級',f"{text_value('risk_level')}（{text_value('risk_score')}）"),('胸徑（來源值）',text_value('diameter')),('樹高（來源值）',text_value('height')),('調查日期',text_value('survey_date')),('掛牌日期',text_value('tagged_date')),('資料建立時間',text_value('source_created_at'))]
    return html.Div([html.Div([html.Span(label),html.Strong(value)],className='detail-row') for label,value in fields])

@app.callback(Output('csv_download','data'),Input('export_button','n_clicks'),Input('district_filter','value'),Input('road_filter','value'),Input('species_filter','value'),Input('issue_filter','value'),Input('status_filter','value'),Input('month_filter','value'),Input('care_only','value'),Input('drill_filter','data'),Input('data_source','value'),prevent_initial_call=True)
def export_data(n_clicks,district,road,species,issue,status,month,care_only,drill_filter,data_source='real'):
    reports = mode_data(data_source)[1]
    if ctx.triggered_id!='export_button':return None
    df=apply_drill_filter(filter_data(district,road,species,issue,status,month,care_only,data_source),drill_filter,data_source)
    if issue != 'all' or status != 'all' or (drill_filter or {}).get('type') == 'issue':
        matching = filter_reports(reports, issue, status, drill_filter)
        df = df[df['tree_id'].isin(matching['tree_id'])]
    df = df.copy()
    df['data_origin'] = '模擬通報／風險' if data_source == 'demo' else '真實資料'
    return dcc.send_data_frame(df.to_csv,'kootree_simulated.csv' if data_source == 'demo' else 'taipei_tree_filtered.csv',index=False,encoding='utf-8-sig')

if __name__=='__main__':
    app.run(debug=False,host='127.0.0.1',port=8050)

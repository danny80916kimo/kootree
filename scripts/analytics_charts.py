"""Chart builders for tree inventory and explicitly simulated operations."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

STATUS_COLORS = {'待巡檢':'#b77948','處理中':'#7e8c75','已結案':'#426448'}

def finish(fig, xlabel, height=370):
    fig.update_layout(height=height, template='plotly_white', paper_bgcolor='#fffdf7', plot_bgcolor='#fffdf7', margin=dict(l=90,r=80,t=45,b=55), font=dict(family='Noto Sans TC, sans-serif',color='#2e4534'), xaxis_title=xlabel, legend=dict(orientation='h',y=1.15,x=0), clickmode='event+select')
    fig.update_xaxes(gridcolor='#e9e8dc',rangemode='tozero')
    fig.update_yaxes(gridcolor='#e9e8dc')
    if not fig.data or all(len(t.x) == 0 for t in fig.data):
        fig.add_annotation(text='目前篩選無資料',xref='paper',yref='paper',x=.5,y=.5,showarrow=False)
    return fig

def inventory_chart(df, column, districts=None, species_colors=None):
    counts = df[column].value_counts()
    if column == 'species':
        top = counts.head(10).copy()
        other = counts.iloc[10:].sum()
        if other:
            top.loc['其他樹種（合計）'] = other
        counts = top
        palette = species_colors or {}
        fig = go.Figure(go.Pie(labels=counts.index, values=counts.values, hole=.60, sort=False,
            marker=dict(colors=[palette.get(name,'#8a948e') for name in counts.index],line=dict(color='white',width=2)),
            textinfo='percent',textposition='inside',insidetextorientation='horizontal',
            hovertemplate='%{label}<br>%{value:,} 棵｜%{percent}<extra></extra>'))
        fig.update_layout(height=410,template='plotly_white', paper_bgcolor='#fffdf7', plot_bgcolor='#fffdf7',margin=dict(l=12,r=12,t=20,b=20),
            font=dict(family='Noto Sans TC, sans-serif',color='#2e4534'),
            legend=dict(orientation='v',x=1,y=.5,yanchor='middle',font=dict(size=11)),hiddenlabels=[],
            annotations=[dict(text=f'{len(df):,}<br><span style="font-size:12px">篩選樹木（棵）</span>',x=.5,y=.5,showarrow=False,font=dict(size=23,color='#294e36'))])
        if df.empty:
            fig.update_layout(annotations=[dict(text='目前篩選無資料',x=.5,y=.5,showarrow=False)])
        return fig
    else:
        # Preserve every district represented in the dataset, including zero matches.
        counts = counts.reindex(sorted(districts if districts is not None else df['district'].dropna().unique()),fill_value=0).sort_values(ascending=False)
    share = counts / max(len(df),1) * 100
    fig = go.Figure(go.Bar(x=counts.values,y=counts.index,orientation='h',marker_color='#426448' if column=='species' else '#81966e',text=[f'{n:,} · {p:.1f}%' for n,p in zip(counts,share)],textposition='outside',cliponaxis=False,customdata=share,hovertemplate='%{y}<br>%{x:,} 棵｜占篩選結果 %{customdata:.1f}%<extra></extra>'))
    fig.update_yaxes(autorange='reversed')
    if len(counts):
        fig.update_xaxes(range=[0,max(counts.max()*1.4,1)])
    return finish(fig,'棵數 · 占目前篩選樹木比例',410)

def issue_chart(df):
    cases=df[df['issue_type']!='無通報']
    order=cases['issue_type'].value_counts().index.tolist()
    fig=go.Figure()
    for status,color in STATUS_COLORS.items():
        counts=cases[cases['issue_status']==status]['issue_type'].value_counts().reindex(order,fill_value=0)
        fig.add_bar(x=counts.values,y=order,orientation='h',name=status,marker_color=color,text=counts.where(counts>0,''),hovertemplate='%{y}<br>'+status+'：%{x:,} 件（模擬）<extra></extra>')
    fig.update_layout(barmode='stack')
    fig.update_yaxes(autorange='reversed')
    return finish(fig,'模擬案件數｜點選長條篩選通報類型')

def rate_chart(df):
    base=df.groupby('district').size()
    cases=df[df['issue_type']!='無通報'].groupby('district').size().reindex(base.index,fill_value=0)
    rate=(cases/base*1000).sort_values(ascending=False)
    average=len(df[df['issue_type']!='無通報'])/max(len(df),1)*1000
    fig=go.Figure(go.Scatter(x=rate.values,y=rate.index,mode='markers+text',marker=dict(size=12,color=['#b77948' if n>average else '#7e8c75' for n in rate]),text=[f'{n:.1f}' for n in rate],textposition='middle right',customdata=np.column_stack([base.reindex(rate.index),cases.reindex(rate.index)]),hovertemplate='%{y}<br>樹木 %{customdata[0]:,} 棵<br>模擬通報 %{customdata[1]:,} 件<br>%{x:.1f} 件／千棵<extra></extra>'))
    fig.add_vline(x=average,line_dash='dot',line_color='#8b6d3f',annotation_text=f'篩選整體 {average:.1f}',annotation_position='top')
    fig.update_yaxes(autorange='reversed')
    if len(rate):fig.update_xaxes(range=[0,max(rate.max()*1.2,1)])
    return finish(fig,'模擬通報件數／千棵（滑鼠移入查看分母）',410)

def priority_chart(df):
    work=df.assign(open_case=df['issue_status'].isin(['待巡檢','處理中']).astype(int),high=df['risk_level'].eq('高').astype(int))
    roads=work.groupby(['district','road']).agg(cases=('open_case','sum'),high=('high','sum'),total=('tree_id','size')).reset_index()
    roads=roads[(roads['cases']>0)|(roads['high']>0)]
    fig=go.Figure(go.Scatter(x=roads['cases'],y=roads['high'],mode='markers',customdata=roads[['district','road','total']].to_numpy(),marker=dict(size=np.clip(np.sqrt(roads['total'])*1.5,8,30),color=roads['high'],colorscale=[[0,'#e8dcc7'],[.5,'#c29870'],[1,'#9d5145']],line=dict(width=1,color='#9a6044'),opacity=.75),hovertemplate='%{customdata[0]} · %{customdata[1]}<br>待處理 %{x} 件｜高風險 %{y} 棵<br>樹木 %{customdata[2]} 棵<extra></extra>'))
    fig.update_yaxes(title='模擬高風險樹木（棵）',rangemode='tozero',dtick=1)
    finish(fig,'模擬待處理通報（件）｜點選路段連動篩選',390)
    # Bubble radii need space beyond zero; explicit ranges prevent clipping.
    max_x = float(roads['cases'].max()) if len(roads) else 1
    max_y = float(roads['high'].max()) if len(roads) else 1
    pad_x = max(2, max_x * .06)
    pad_y = max(.5, max_y * .10)
    fig.update_xaxes(range=[-pad_x, max_x + pad_x], rangemode='normal', tick0=0, zeroline=False)
    fig.update_yaxes(range=[-pad_y, max_y + pad_y], rangemode='normal', tick0=0, dtick=1, zeroline=False)
    return fig

def age_chart(df):
    pending=df[df['issue_status'].isin(['待巡檢','處理中'])]
    bins=pd.cut(pending['case_age_days'],[-1,7,14,30,float('inf')],labels=['0–7 天','8–14 天','15–30 天','31 天以上'])
    counts=bins.value_counts(sort=False)
    fig=go.Figure(go.Bar(x=counts.index,y=counts.values,marker_color=['#426448','#99ad7c','#b49b57','#a45547'],text=counts.values,textposition='outside'))
    fig.update_yaxes(title='模擬待處理件數',rangemode='tozero')
    return finish(fig,'模擬案件目前經過天數',390)

"""Reference dashboard charts, calculated from complete Supabase records."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

STATUS_COLORS = {'待確認':'#b77948','已確認':'#7e8c75','已排除':'#426448'}


def finish(fig, xlabel, height=390):
    fig.update_layout(height=height, template='plotly_white', paper_bgcolor='#fffdf7', plot_bgcolor='#fffdf7', margin=dict(l=90,r=65,t=45,b=55), font=dict(family='Noto Sans TC, sans-serif',color='#2e4534'), xaxis_title=xlabel, legend=dict(orientation='h',y=1.15,x=0),clickmode='event+select')
    fig.update_xaxes(gridcolor='#e9e8dc',rangemode='tozero')
    fig.update_yaxes(gridcolor='#e9e8dc')
    return fig


def empty_chart(message, xlabel=''):
    fig=finish(go.Figure(),xlabel)
    fig.add_annotation(text=message,xref='paper',yref='paper',x=.5,y=.5,showarrow=False)
    return fig


def issue_chart(reports, simulated=False):
    if reports.empty:return empty_chart('目前篩選沒有通報資料','通報件數')
    order=reports.issue_type.value_counts().index.tolist(); fig=go.Figure()
    colors=dict(STATUS_COLORS)
    colors.update({str(status):'#8a948e' for status in reports.issue_status.unique() if status not in colors})
    for status,color in colors.items():
        counts=reports.loc[reports.issue_status.eq(status),'issue_type'].value_counts().reindex(order,fill_value=0)
        fig.add_bar(x=counts.values,y=order,orientation='h',name=status,marker_color=color,text=counts.where(counts>0,''),hovertemplate='%{y}<br>'+status+'：%{x:,} 件'+('（模擬）' if simulated else '')+'<extra></extra>')
    fig.update_layout(barmode='stack');fig.update_yaxes(autorange='reversed')
    return finish(fig,'通報件數｜點選長條篩選通報類型')


def rate_chart(population,reports):
    if population.empty:return empty_chart('目前篩選範圍無樹木，無法計算比率','件／千棵')
    base=population.groupby('district').size()
    counts=reports.merge(population[['tree_id','district']],on='tree_id').groupby('district').size().reindex(base.index,fill_value=0)
    rate=(counts/base*1000).sort_values(ascending=False); average=int(counts.sum())/len(population)*1000
    fig=go.Figure(go.Scatter(x=rate.values,y=rate.index,mode='markers+text',marker=dict(size=12,color=['#b77948' if n>average else '#7e8c75' for n in rate]),text=[f'{n:.2f}' for n in rate],textposition='middle right',customdata=np.column_stack([base.reindex(rate.index),counts.reindex(rate.index)]),hovertemplate='%{y}<br>樹木 %{customdata[0]:,} 棵<br>通報 %{customdata[1]:,} 件<br>%{x:.2f} 件／千棵<extra></extra>'))
    fig.add_vline(x=average,line_dash='dot',line_color='#8b6d3f',annotation_text=f'篩選整體 {average:.2f}',annotation_position='top')
    fig.update_yaxes(autorange='reversed');fig.update_xaxes(range=[0,max(float(rate.max())*1.2,1)])
    return finish(fig,'通報件數／千棵（滑鼠移入查看分母）',410)


def priority_chart(population,reports):
    base=population.groupby(['district','road']).size().rename('total')
    pending=reports[reports.issue_status.eq('待確認')].merge(population[['tree_id','district','road']],on='tree_id').groupby(['district','road']).size().rename('cases')
    high=population[population.risk_level.eq('高')].groupby(['district','road']).size().rename('high')
    roads=pd.concat([base,pending,high],axis=1).fillna(0).reset_index()
    roads=roads[(roads.cases>0)|(roads.high>0)]
    if roads.empty:return empty_chart('目前範圍沒有待確認通報或已評估的高風險樹木','待確認通報（件）')
    fig=go.Figure(go.Scatter(x=roads.cases,y=roads.high,mode='markers',customdata=roads[['district','road','total']].to_numpy(),marker=dict(size=np.clip(np.sqrt(roads.total)*1.5,8,30),color=roads.high,colorscale=[[0,'#e8dcc7'],[.5,'#c29870'],[1,'#9d5145']],line=dict(width=1,color='#9a6044'),opacity=.75),hovertemplate='%{customdata[0]} · %{customdata[1]}<br>待確認 %{x} 件｜高風險 %{y} 棵<br>樹木 %{customdata[2]} 棵<extra></extra>'))
    finish(fig,'待確認通報（件）｜點選路段連動篩選')
    fig.update_xaxes(range=[-2,max(float(roads.cases.max())*1.1,1)+2],zeroline=False)
    fig.update_yaxes(title='已評估高風險樹木（棵）',range=[-.5,max(float(roads.high.max())*1.1,1)+.5],dtick=1,zeroline=False)
    return fig


def age_chart(reports):
    pending=reports[reports.issue_status.eq('待確認')]
    if pending.empty:return empty_chart('目前範圍沒有待確認通報','通報經過天數')
    valid=pending.case_age_days.dropna()
    if valid.empty:return empty_chart('通報日期未完整提供，無法計算天數','通報經過天數')
    bins=pd.cut(valid,[-1,7,14,30,float('inf')],labels=['0–7 天','8–14 天','15–30 天','31 天以上'])
    counts=bins.value_counts(sort=False)
    fig=go.Figure(go.Bar(x=counts.index,y=counts.values,marker_color=['#426448','#99ad7c','#b49b57','#a45547'],text=counts.values,textposition='outside'))
    finish(fig,'待確認通報目前經過天數');fig.update_yaxes(title='待確認通報件數',rangemode='tozero')
    if len(valid)!=len(pending):fig.add_annotation(text=f'{len(pending)-len(valid)} 件日期缺漏未納入',xref='paper',yref='paper',x=1,y=1.12,showarrow=False)
    return fig


def report_history(population,reports):
    columns=['tree_code','district','road','species','risk_score','risk_level']
    frame=reports.merge(population[['tree_id']+columns],on='tree_id',how='inner',suffixes=('_report',''))
    frame['reported_date']=pd.to_datetime(frame.created_at,errors='coerce',utc=True).dt.strftime('%Y-%m-%d')
    frame['data_origin']='Supabase 模擬通報' if 'risk_score_report' in frame else 'Supabase 真實通報'
    return frame


def history_chart(reports):
    dates=pd.to_datetime(reports.created_at,errors='coerce',utc=True).dropna()
    if dates.empty:return empty_chart('尚無可用的通報日期；未提供結案紀錄','月份')
    counts=dates.dt.strftime('%Y-%m').value_counts().sort_index()
    fig=go.Figure(go.Bar(x=counts.index,y=counts.values,name='新增通報',marker_color='#b77948'))
    finish(fig,'通報月份',320);fig.update_yaxes(title='通報件數',dtick=1)
    fig.add_annotation(text='未提供結案日期，不推估結案趨勢',xref='paper',yref='paper',x=1,y=1.12,xanchor='right',showarrow=False,font=dict(size=11))
    return fig

"""Complete-population summary charts for the current dashboard selection."""
import pandas as pd
import plotly.graph_objects as go

DISTRICTS = ['中正區','大同區','中山區','松山區','大安區','萬華區','信義區','士林區','北投區','內湖區','南港區','文山區']
PALETTE = ['#365b40','#9d7b50','#899b60','#b97e60','#7d92a1',
           '#99869a','#70968d','#b5a05d','#ac727a','#6c8179','#929b93']
PAPER = '#fffdf7'
INK = '#31543e'


def labels(series, fallback):
    return series.fillna(fallback).astype(str).str.strip().replace('', fallback)


def species_donut(frame):
    counts = labels(frame['species'], '未分類').value_counts()
    top = counts.head(10)
    chart_labels = top.index.tolist()
    values = top.astype(int).tolist()
    remainder = int(counts.iloc[10:].sum())
    if remainder:
        chart_labels.append('其他樹種（合計）')
        values.append(remainder)
    chart = go.Figure()
    if values:
        colors = PALETTE[:len(top)] + ([PALETTE[-1]] if remainder else [])
        chart.add_trace(go.Pie(
            labels=chart_labels, values=values, hole=.52, sort=False,
            direction='clockwise', rotation=0,
            marker={'colors':colors,'line':{'color':PAPER,'width':2}},
            textinfo='percent', textposition='inside',
            textfont={'size':12,'color':['#fffdf7' if color == PALETTE[0] else '#21372a' for color in colors]},
            insidetextorientation='auto',
            hovertemplate='%{label}<br>%{value:,} 棵 · %{percent}<extra></extra>',
        ))
    chart.update_layout(
        height=520, margin={'l':8,'r':8,'t':25,'b':20},
        paper_bgcolor=PAPER, plot_bgcolor=PAPER,
        font={'family':'Noto Sans TC, Arial, sans-serif','color':INK},
        uniformtext={'minsize':10,'mode':'hide'},
        legend={'orientation':'v','x':1.01,'y':.5,'yanchor':'middle','font':{'size':12}},
        xaxis={'visible':False}, yaxis={'visible':False},
        annotations=[
            {'text':f'{len(frame):,}','x':.5,'y':.52,'xref':'paper','yref':'paper',
             'showarrow':False,'font':{'size':30,'color':INK}},
            {'text':'篩選樹木（棵）','x':.5,'y':.40,'xref':'paper','yref':'paper',
             'showarrow':False,'font':{'size':13,'color':INK}},
        ],
    )
    if not values:
        chart.add_annotation(text='目前條件無樹木',x=.5,y=.22,xref='paper',yref='paper',showarrow=False)
    return chart


def district_distribution(frame):
    counts = labels(frame['district'], '未提供').value_counts()
    complete = counts.reindex(DISTRICTS, fill_value=0)
    # Preserve unexpected labels rather than silently dropping their trees.
    extra = counts.loc[~counts.index.isin(DISTRICTS)]
    if len(extra):
        complete = pd.concat([complete, extra])
    complete = complete.sort_values(ascending=False, kind='stable')
    total = len(frame)
    percentages = complete / total * 100 if total else complete.astype(float)
    text = [f'{int(count):,} · {percentage:.1f}%' for count,percentage in zip(complete,percentages)]
    chart = go.Figure(go.Bar(
        x=complete.values, y=complete.index, orientation='h',
        marker_color='#849971', text=text, textposition='outside', cliponaxis=False,
        textfont={'size':12,'color':INK}, customdata=percentages.to_numpy(),
        hovertemplate='%{y}<br>%{x:,} 棵 · %{customdata:.1f}%<extra></extra>',
    ))
    maximum = float(complete.max()) if len(complete) else 0
    chart.update_layout(
        height=520, margin={'l':74,'r':25,'t':25,'b':65}, bargap=.2,
        paper_bgcolor=PAPER, plot_bgcolor=PAPER,
        font={'family':'Noto Sans TC, Arial, sans-serif','color':INK},
        showlegend=False,
        xaxis={'title':'棵數 · 占目前篩選樹木比例','gridcolor':'#e8e7dc',
               'zeroline':False,'range':[0,maximum*1.4 if maximum else 1],'tickformat':'~s'},
        yaxis={'title':'','autorange':'reversed','showgrid':False,'automargin':True},
    )
    return chart

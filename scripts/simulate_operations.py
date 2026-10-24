"""Deterministic synthetic operations, never official maintenance records."""
import numpy as np
import pandas as pd

AS_OF = pd.Timestamp('2026-10-21')

def generate_operations(trees):
    df = trees.copy()
    rng = np.random.default_rng(20261021)
    has_case = df['issue_type'].ne('無通報')
    closed = df['issue_status'].eq('已結案') & has_case
    ages = pd.to_numeric(df['case_age_days']).astype(int)
    # Open cases retain their dashboard age. Closed cases span the last six months.
    offsets = np.where(closed, rng.integers(22, 180, len(df)), ages)
    reported = pd.Series(AS_OF - pd.to_timedelta(offsets, unit='D'), index=df.index)
    closed_dates = reported + pd.to_timedelta(np.minimum(rng.integers(1, 22, len(df)), offsets), unit='D')
    df['case_id'] = [f'SIM-{i+1:06d}' if has else '' for i,has in enumerate(has_case)]
    df['reported_date'] = reported.dt.strftime('%Y-%m-%d').where(has_case, '')
    df['closed_date'] = closed_dates.dt.strftime('%Y-%m-%d').where(closed, '')
    df['inspection_date'] = (AS_OF - pd.to_timedelta(rng.integers(0, 120, len(df)),unit='D')).strftime('%Y-%m-%d')
    # An in-progress/closed case must have an inspection after its report.
    inspected = has_case & df['issue_status'].isin(['處理中','已結案'])
    df.loc[inspected,'inspection_date'] = reported[inspected].dt.strftime('%Y-%m-%d')
    df['team'] = rng.choice(['模擬東區班','模擬西區班','模擬南區班','模擬北區班'],len(df))
    df['work_action'] = df['issue_type'].map({'落枝枯枝':'枯枝修剪','側枝遮擋':'側枝整理','根系隆起':'根系與鋪面評估','疑似病蟲害':'現地確認病蟲害徵象','落果清理':'果實清掃','種子飛絮':'飛絮觀察與環境清理','樹木傾斜':'支撐與樹勢評估'}).fillna('例行觀察')
    df['simulation_note'] = '全部案件與履歷為模擬資料；基準日 2026-10-21，非實際養護紀錄'
    return df

def monthly_trend(df):
    months = pd.period_range(end=AS_OF.to_period('M'), periods=6, freq='M').astype(str)
    result = pd.DataFrame({'month':months})
    for column, target in [('reported_date','reported'),('closed_date','closed')]:
        counts = df.loc[df[column].ne(''),column].str[:7].value_counts()
        result[target] = result['month'].map(counts).fillna(0).astype(int)
    return result

def tree_events(row):
    events = [(row['inspection_date'], '模擬巡檢｜'+row['team'])]
    if row['reported_date']:
        events.append((row['reported_date'], '模擬通報｜'+row['issue_type']))
        if row['issue_status'] in ['處理中','已結案']:
            events.append((row['reported_date'], '模擬派工｜'+row['work_action']))
        if row['closed_date']:
            events.append((row['closed_date'], '模擬完工結案｜'+row['work_action']))
        else:
            events.append((AS_OF.strftime('%Y-%m-%d'), '模擬目前狀態｜'+row['issue_status']))
    return sorted(events, key=lambda event:event[0])


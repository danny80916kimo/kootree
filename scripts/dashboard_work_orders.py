"""Read actual or explicitly simulated work orders; never invent missing jobs."""
from functools import lru_cache
import pandas as pd
from scripts.supabase_data import load_rows, read_session

COLUMNS=['id','tree_location_id','report_id','job_status','action','team','created_at','inspection_at','completed_at','is_simulated']


def normalize_work_orders(rows):
    if not rows:return pd.DataFrame(columns=COLUMNS)
    frame=pd.DataFrame(rows)
    if set(COLUMNS)-set(frame.columns):raise ValueError('養護工單缺少必要欄位')
    if frame.id.isna().any() or frame.id.duplicated().any() or frame.tree_location_id.isna().any():raise ValueError('工單編號或樹籍關聯不完整')
    if not frame.is_simulated.map(lambda value:type(value) is bool).all():raise ValueError('工單資料性質未標示')
    if not frame.job_status.isin(['待派工','處理中','已完成','已取消']).all():raise ValueError('工單狀態不完整')
    created=pd.to_datetime(frame.created_at,errors='coerce',utc=True)
    completed=pd.to_datetime(frame.completed_at,errors='coerce',utc=True)
    if created.isna().any() or (completed<created).any():raise ValueError('工單日期不合理')
    if (frame.job_status.eq('已完成') & completed.isna()).any():raise ValueError('完成工單缺少完成日期')
    frame['tree_id']=frame.tree_location_id.astype(str)
    return frame


@lru_cache(maxsize=1)
def load_work_orders():
    try:
        with read_session() as session:
            rows=load_rows(session=session,table='dashboard_work_orders',select=','.join(COLUMNS))
        return normalize_work_orders(rows),'Supabase 養護工單已連線'
    except ValueError:
        return normalize_work_orders([]),'Supabase 尚未提供可讀取的養護工單；不推估班組、巡檢或完工紀錄。'

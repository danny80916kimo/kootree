import pytest
from scripts.dashboard_work_orders import normalize_work_orders


def row(**changes):
    value=dict(id='w1',tree_location_id='tree-a',report_id='r1',job_status='處理中',action='現場評估',team='測試班組',created_at='2026-10-20T00:00:00Z',inspection_at=None,completed_at=None,is_simulated=False)
    value.update(changes);return value


def test_work_status_is_independent_of_report_confirmation():
    data=normalize_work_orders([row()])
    assert data.iloc[0].job_status=='處理中'
    assert data.iloc[0].tree_id=='tree-a'
    assert data.iloc[0].completed_at is None


def test_finished_jobs_need_a_real_completion_timestamp():
    with pytest.raises(ValueError,match='完成日期'):
        normalize_work_orders([row(job_status='已完成')])
    with pytest.raises(ValueError,match='日期不合理'):
        normalize_work_orders([row(job_status='已完成',completed_at='2026-10-19T00:00:00Z')])
    with pytest.raises(ValueError,match='資料性質'):
        normalize_work_orders([row(is_simulated='false')])

import pandas as pd
from scripts.simulate_operations import generate_operations, monthly_trend, AS_OF

def test_simulated_dates_and_counts():
    source = pd.DataFrame({'tree_id':['a','b','c','d'], 'issue_type':['落枝枯枝','側枝遮擋','病蟲害','無通報'], 'issue_status':['待巡檢','處理中','已結案','無案件'], 'case_age_days':[12,5,8,0]})
    df = generate_operations(source)
    pd.testing.assert_frame_equal(df, generate_operations(source))
    assert df.loc[0,'reported_date'] == '2026-10-09'
    assert df.loc[1,'inspection_date'] >= df.loc[1,'reported_date']
    assert df.loc[2,'reported_date'] <= df.loc[2,'closed_date'] <= str(AS_OF.date())
    assert (df.loc[[0,1,3],'closed_date'] == '').all()
    assert df.loc[3,'case_id'] == ''
    trend = monthly_trend(df)
    assert trend['reported'].sum() == 3
    assert trend['closed'].sum() == 1

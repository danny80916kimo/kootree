import pandas as pd
from scripts.data_loader import transform_trees

def test_twd97_conversion():
    # Approximate Taipei coordinate near city centre
    df = pd.DataFrame([{'TreeID':'TEST-1','Dist':'中正區','Region':'測試路','TreeType':'榕樹','TWD97X':303000,'TWD97Y':2770000}])
    result = transform_trees(df)
    assert len(result)==1
    assert 121.2 < result.iloc[0]['longitude'] < 121.9
    assert 24.8 < result.iloc[0]['latitude'] < 25.3

def test_required_fields():
    try:
        transform_trees(pd.DataFrame({'TreeID':['1']}))
    except ValueError as error:
        assert '缺少必要欄位' in str(error)
    else:
        raise AssertionError('Expected ValueError')

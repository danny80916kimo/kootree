import pandas as pd
import pytest

from scripts.dashboard_charts import DISTRICTS, species_donut, district_distribution


def test_donut_top_ten_plus_other_conserves_every_tree():
    names = [f'樹種{i}' for i in range(12) for _ in range(i+1)]
    frame = pd.DataFrame({'species': names})
    chart = species_donut(frame)
    pie = chart.data[0]
    assert len(pie.labels) == 11
    assert pie.labels[-1] == '其他樹種（合計）'
    assert pie.values[-1] == 3
    assert sum(pie.values) == len(frame)
    assert chart.layout.annotations[0].text == f'{len(frame):,}'


def test_donut_single_species_has_no_spurious_other_slice():
    chart = species_donut(pd.DataFrame({'species':['榕樹']*3}))
    assert list(chart.data[0].labels) == ['榕樹']
    assert list(chart.data[0].values) == [3]


def test_district_chart_contains_all_twelve_even_when_filtered_to_one():
    chart = district_distribution(pd.DataFrame({'district':['大安區']*3}))
    trace = chart.data[0]
    assert len(trace.y) == 12
    assert set(trace.y) == set(DISTRICTS)
    assert trace.y[0] == '大安區'
    assert trace.customdata[0] == 100
    assert sum(trace.x) == 3
    assert sum(trace.customdata) == pytest.approx(100)
    assert list(trace.x).count(0) == 11


def test_unknown_district_is_preserved_instead_of_silently_dropped():
    chart = district_distribution(pd.DataFrame({'district':['大安區',None]}))
    assert '未提供' in chart.data[0].y
    assert sum(chart.data[0].x) == 2
    assert sum(chart.data[0].customdata) == pytest.approx(100)


def test_empty_selection_has_zero_total_without_nan_percentages():
    frame = pd.DataFrame(columns=['district','species'])
    donut = species_donut(frame)
    assert not donut.data
    assert donut.layout.annotations[0].text == '0'
    district = district_distribution(frame)
    assert len(district.data[0].y) == 12
    assert list(district.data[0].customdata) == [0]*12

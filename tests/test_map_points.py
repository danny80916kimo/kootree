import pandas as pd
from scripts.map_points import select_map_points


def test_overview_preserves_every_individual_tree():
    trees = pd.DataFrame({'tree_id': range(9000), 'latitude': [25.05] * 9000,
                          'longitude': [121.51] * 9000})
    points, clusters = select_map_points(trees)
    assert clusters is None
    assert len(points) == 9000
    assert points.tree_id.tolist() == trees.tree_id.tolist()


def test_street_view_includes_all_trees_inside_bounds():
    trees = pd.DataFrame({'tree_id': range(9001), 'latitude': [25.05] * 9001,
                          'longitude': [121.51] * 9000 + [121.6]})
    view = {'mapbox.zoom': 16, 'mapbox._derived': {'coordinates': [
        [121.50, 25.04], [121.52, 25.04], [121.52, 25.06], [121.50, 25.06]]}}
    points, clusters = select_map_points(trees, view)
    assert clusters is None
    assert len(points) == 9000

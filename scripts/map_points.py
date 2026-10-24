"""Select every individual tree within the map viewport, without sampling."""


def select_map_points(df, view=None):
    view = view or {}
    coordinates = view.get('mapbox._derived', {}).get('coordinates')
    visible = df.dropna(subset=['latitude', 'longitude'])
    if coordinates:
        west, east = min(p[0] for p in coordinates), max(p[0] for p in coordinates)
        south, north = min(p[1] for p in coordinates), max(p[1] for p in coordinates)
        visible = visible[visible.longitude.between(west, east) & visible.latitude.between(south, north)]
    return visible, None

"""
Display a `geopandas.GeoDataFrame` object using the plotly and Mapboxplot API.

Attributes:
    MAPBOX_ACCESS_TOKEN (str): the public key to access mapboxplot via [plotly](https://plot.ly/python/scattermapbox/)

Examples:
    ```
    from explorator import geoplot
    import geopandas as gpd
    gdf = gpd.read_file(gpd.datasets.get_path('naturalearth_cities'))
    gdf.geoplot()
    ```

TODO:
    https://plot.ly/python/animations/#offline-mode

"""
import os
import math
import json

import geopandas as gpd
from plotly import graph_objs as go
from plotly.offline import iplot

MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN', None)


def get_auto_zoom(gdf):
    lats = gdf.centroid.y
    lons = gdf.centroid.x
    span = 6.5 - math.ceil(max(max(lats) - min(lats),
                               max(lons) - min(lons))) / 10
    span = 1 if span < 1 else span
    return span


def plot_markers_with_mapbox(gdf, text=None, center=None, zoom=None, size=None, mode='markers', color='darkblue',
                             style='basic', mapbox_access_token=None, return_fig=False, opacity=.5,
                             animate_by=None):
    """
    Display geometry POINTS on a map with text columns as hoverinfo

    Args:
        gdf (geopandas.GeoDataFrame):
        text (list):
        center (tuple):
        zoom (int): in [0, 10]
        size (int): size of the markers
        mode (str): 'markers' or 'markers+text'
        color (str):
        style (str): style of the map opassed to go.Layout 'satellite-streets', 'light', 'dark', 'basic', 'outdoors'
            or 'satellite'
        mapbox_access_token (str): to override the environment variable if needed.

    References:
       https://plot.ly/python/reference/#scattermapbox
       https://plot.ly/python/scattermapbox/
    """
    if mapbox_access_token is None:
        mapbox_access_token = MAPBOX_ACCESS_TOKEN
    if center is None:
        center = get_auto_center(gdf)
    if zoom is None:
        zoom = get_auto_zoom(gdf)
    if text:
        text_col = text
        text = ['_'.join(map(str, vv)) for _, vv in gdf[text].iterrows()]

    # Centroids make sure iut works with polygons too
    lon = gdf.centroid.x
    lat = gdf.centroid.y

    trace = go.Scattermapbox(lat=lat, lon=lon, marker=go.Marker(color=color, size=size),
                             mode=mode, text=text, hoverinfo='text')

    layout = go.Layout(
        autosize=True,
        hovermode='closest',
        mapbox=dict(
            accesstoken=mapbox_access_token,
            bearing=0,
            center=center,
            pitch=0,
            zoom=zoom,
            style=style
        ),
    )
    # Add shapes if exists
    shape_gdf = gdf.loc[gdf.geom_type != 'Point']
    layers = gdf_to_plotly_layers(shape_gdf, opacity=opacity, color=color)
    layout.mapbox['layers'] = layers

    fig = go.Figure(data=[trace], layout=layout)
    if animate_by:
        fig = animate(gdf, by=animate_by, fig=fig, text=text_col, opacity=opacity,
                      size=size, color=color, mode=mode)

    if return_fig:
        return fig
    iplot(fig)


def animate(df, by, fig=None, **kwargs):
    # Config for animate
    play_pause_menus = [{'buttons': [{'args': [None, {'fromcurrent': True}],
                                      'label': 'Play',
                                      'method': 'animate'}],
                         'direction': 'left',
                         'pad': {'r': 20, 't': 40},
                         'showactive': False,
                         'type': 'buttons',
                         'x': 0.1,
                         'y': -0.1},
                        {'buttons': [{'args': [[None],
                                               {'frame': {'duration': 0, 'redraw': False},
                                                'mode': 'immediate',
                                                'transition': {'duration': 0}}],
                                      'label': 'Pause',
                                      'method': 'animate'}],
                         'direction': 'left',
                         'pad': {'r': 20, 't': 40},
                         'showactive': False,
                         'type': 'buttons',
                         'x': 0.1,
                         'y': 0.05}]
    sliders = dict(currentvalue=dict(prefix='{}: '.format(', '.join([by])),
                                     xanchor='right'),
                   transition=dict(duration=300),
                   pad=dict(b=10,
                            t=30),
                   len=0.9,
                   x=0.1,
                   steps=[])

    frames = []
    grouped = df.groupby(by, as_index=False)
    # Compute once for all the groups
    zoom, center = get_auto_zoom(df), get_auto_center(df)
    for ii, (key, values) in enumerate(grouped):
        group_fig = values.drop([by], 1).iplot(
            return_fig=True, zoom=zoom, center=center, **kwargs)
        frames.append({'data': group_fig['data'], 'name': str(key)})
        step = dict(args=[[str(key)],
                          dict(frame=dict(duration=300),
                               mode='immediate',
                               transition=dict(duration=300))],
                    label=str(key),
                    method='animate')
        sliders['steps'].append(step)
        if ii == 0 and fig is None:
            # Init simple fig
            fig = group_fig

    # Add frames and config
    fig['frames'] = frames
    fig.layout.sliders = [sliders]
    fig.layout.updatemenus = play_pause_menus

    return fig


def get_auto_center(gdf):
    mean_lon = gdf.total_bounds[::2].mean()
    mean_lat = gdf.total_bounds[1::2].mean()
    center = dict(lon=mean_lon, lat=mean_lat)

    return center


def gdf_to_plotly_layers(gdf, default_layer=None, **kwargs):
    """
    Create a FeatureCollection for each element of gdf.geometry and add it to a layer

    Args:
        gdf ():
        default_layer (dict):
        **kwargs (): to override the default layer

    Notes:
        Unlike a standard FeatureCollection, if there is one geometry only it should still be in a list

    References:
        for kwargs : https://plot.ly/python/reference/#layout-mapbox

    Returns:
        list
    """
    if default_layer is None:
        default_layer = dict(sourcetype='geojson',
                             type='fill',
                             color='red',
                             opacity=.3,
                             fill=dict(outlinecolor='red')
                             )
        default_layer.update(kwargs)

    geojson_dict = json.loads(gdf.to_json())
    layers = []
    for geometry in geojson_dict['features']:
        layer = default_layer.copy()
        flattened_geojson = dict(features=[geometry], type='FeatureCollection')
        layer['source'] = flattened_geojson
        layers.append(layer)
    return layers

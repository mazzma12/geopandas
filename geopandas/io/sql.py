import pandas as pd
import shapely.wkb

from geopandas import GeoDataFrame
from geopandas.tools.util import crs_to_srid


def read_postgis(sql, con, geom_col='geom', crs=None, hex_encoded=True,
                 index_col=None, coerce_float=True, params=None):
    """
    Returns a GeoDataFrame corresponding to the result of the query
    string, which must contain a geometry column.

    Parameters
    ----------
    sql : string
        SQL query to execute in selecting entries from database, or name
        of the table to read from the database.
    con : DB connection object or SQLAlchemy engine
        Active connection to the database to query.
    geom_col : string, default 'geom'
        column name to convert to shapely geometries
    crs : dict or str, optional
        CRS to use for the returned GeoDataFrame; if not set, tries to
        determine CRS from the SRID associated with the first geometry in
        the database, and assigns that to all geometries.
    hex_encoded : bool, optional
        Whether the geometry is in a hex-encoded string. Default is True,
        standard for postGIS. Use hex_encoded=False for sqlite databases.

    See the documentation for pandas.read_sql for further explanation
    of the following parameters:
    index_col, coerce_float, params

    Returns
    -------
    GeoDataFrame

    Example
    -------
    >>> sql = "SELECT geom, kind FROM polygons;"
    >>> df = geopandas.read_postgis(sql, con)
    """

    df = pd.read_sql(sql, con, index_col=index_col, coerce_float=coerce_float,
                     params=params)

    if geom_col not in df:
        raise ValueError("Query missing geometry column '{}'".format(geom_col))

    def load_geom(x):
        if isinstance(x, bytes):
            return shapely.wkb.loads(x, hex=hex_encoded)
        else:
            return shapely.wkb.loads(str(x), hex=hex_encoded)

    geoms = df[geom_col].apply(load_geom)
    df[geom_col] = geoms

    if crs is None:
        if len(geoms) > 0:
            srid = shapely.geos.lgeos.GEOSGetSRID(geoms[0]._geom)
            # if no defined SRID in geodatabase, returns SRID of 0
            if srid != 0:
                crs = {"init": "epsg:{}".format(srid)}

    return GeoDataFrame(df, crs=crs, geometry=geom_col)


def write_postgis(df, name, con, **kwargs):
    """
    Write a GeoDataFrame to a PostGIS table.

    Tables can be newly created, appended to, or overwritten.
    The type and the crs of the GeoDataFrame geometry is converted automatically to match PostGIS format.
    This behavior can be changed as shown in the Examples section.

    Parameters
    ----------
    df : GeoDataFrame
    name : string
        Name of PostGIS table
    con : sqlalchemy.engine.Engine or DB connection object
        Active connection to the database.
    kwargs :
        passed to pandas.to_sq. See documentation for available parameters

    Raises
    ------
    ValueError
        When the table already exists and `if_exists` is 'fail' (the
        default).

    See Also
    --------
    pandas.read_sql : pass kwargs to this function

    References
    ----------
    .. [1] http://docs.sqlalchemy.org
    .. [2] https://www.python.org/dev/peps/pep-0249/
    .. [3] https://geoalchemy-2.readthedocs.io/en/latest/

    Notes
    ------
    Geometry is converted to `WKTElements` object using `geoalchemy2` library.
    The original frame is copied to not mutate it.
    Only one column with shapely objets is supported.

    Examples:
    ---------
    Create a connection object to PostGIS (5432 is the default port)
    >>> from sqlalchemy import create_engine
    >>> engine = create_engine('postgis://user:password@domain_name/5432', echo=False)
    >>> con = engine.connect()

    Create a PostGIS table with the type and the crs defined in the GeoDataFrame
    >>> table_name = 'test'
    >>> write_postgis(df, table_name, con, if_exists='replace')

    Override PostGIS geometry type and crs using the geoalchemy library
    >>> import geoalchemy2
    >>> write_postgis(df, table_name, con, dtype={'geometry': geoalchemy2.Geometry('POLYGON', 4326)})
    """
    from geoalchemy2 import WKTElement, Geometry

    temp_df = df.copy()
    postgis_geom_type = _geom_type_to_postgis(temp_df.geometry)
    srid = crs_to_srid(temp_df.crs)
    kwargs.setdefault('dtype', {})
    kwargs['dtype'].setdefault(
        temp_df.geometry.name, Geometry(postgis_geom_type, srid=srid))
    geom = temp_df.geometry

    # Do not use `geoalchemy.sql.from_shape()` 
    # See https://github.com/geoalchemy/geoalchemy2/issues/132
    temp_df[temp_df.geometry.name] = geom.map(
        lambda x: WKTElement(x.wkt, srid=srid))
    temp_df.to_sql(name, con, **kwargs)


def _geom_type_to_postgis(gdf):
    """
    Convert the geometry type of a GeoDataFrame to the PostGIS equivalent one.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame

    Notes
    -----
    Call to method `geopandas.GeoDataFrame.geom_type()` to get the geometry type

    Returns
    -------
    postgis_geom_type: str
        The equivalent of the geometry type in the PostGIS format
    """
    if all(gdf.geom_type == 'Polygon'):
        postgis_geom_type = 'POLYGON'
    elif all(gdf.geom_type == 'MultiPolygon'):
        postgis_geom_type = 'MULTIPOLYGON'
    elif all(gdf.geom_type == 'Point'):
        postgis_geom_type = 'POINT'
    elif all(gdf.geom_type == 'LineString'):
        postgis_geom_type = 'LINESTRING'
    elif all(gdf.geom_type == 'MultiPoint'):
        postgis_geom_type = 'MULTIPOINT'
    elif all(gdf.geom_type == 'GeometryCollection'):
        postgis_geom_type = 'GEOMETRYCOLLECTION'
    elif all(gdf.geom_type == 'MultiLineString'):
        postgis_geom_type = 'MULTILINESTRING'
    else:
        postgis_geom_type = 'GEOMETRY'
    return postgis_geom_type

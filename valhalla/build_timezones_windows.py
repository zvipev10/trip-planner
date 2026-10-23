"""Build regional timezone polygons using the SQLite/SpatiaLite DLLs bundled in the pinned Windows wheel."""
import ctypes,os,json,urllib.request,zipfile,sys
import valhalla
from pathlib import Path
from shapely.geometry import shape,box
root=Path(sys.argv[1]).resolve(strict=True)
libs=Path(valhalla.__file__).resolve().parent.parent/'pyvalhalla.libs';handle=os.add_dll_directory(str(libs))
sqlite=ctypes.CDLL(str(next(libs.glob('sqlite3-*.dll')))); spatial=ctypes.CDLL(str(next(libs.glob('spatialite-*.dll'))))
sqlite.sqlite3_open.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_void_p)];sqlite.sqlite3_exec.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_char_p)];sqlite.sqlite3_close.argtypes=[ctypes.c_void_p]
spatial.spatialite_alloc_connection.restype=ctypes.c_void_p;spatial.spatialite_init_ex.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]
url='https://github.com/evansiroky/timezone-boundary-builder/releases/download/2026d/timezones-with-oceans-1970.geojson.zip'
p=root/'timezones-2026d.zip'
if not p.exists():urllib.request.urlretrieve(url,p)
with zipfile.ZipFile(p) as z:d=json.loads(z.read(next(n for n in z.namelist() if n.endswith('.json') or n.endswith('.geojson'))))
db=ctypes.c_void_p();assert sqlite.sqlite3_open(str(root/'timezones.sqlite').encode(),ctypes.byref(db))==0
cache=spatial.spatialite_alloc_connection();spatial.spatialite_init_ex(db,cache,0)
def execute(sql):
 err=ctypes.c_char_p();rc=sqlite.sqlite3_exec(db,sql.encode(),None,None,ctypes.byref(err));assert rc==0,(rc,err.value)
execute("SELECT InitSpatialMetaData(1);CREATE TABLE tz_world (PK_UID INTEGER PRIMARY KEY AUTOINCREMENT, tzid TEXT); SELECT AddGeometryColumn('tz_world','geom',4326,'MULTIPOLYGON','XY');")
count=0;region=box(33,28,37,35)
for f in d['features']:
 geom=shape(f['geometry'])
 if not geom.intersects(region):continue
 geom=geom.intersection(region)
 if geom.geom_type=='Polygon':
  from shapely.geometry import MultiPolygon
  geom=MultiPolygon([geom])
 tzid=f['properties']['tzid'].replace("'","''");execute(f"INSERT INTO tz_world(tzid,geom) VALUES ('{tzid}',GeomFromText('{geom.wkt}',4326));");count+=1
execute("SELECT CreateSpatialIndex('tz_world','geom'); VACUUM; ANALYZE;")
sqlite.sqlite3_close(db)
print('Built timezone database:',count,'regional polygons')

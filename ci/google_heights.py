"""Building heights for Calicut from Google Open Buildings 2.5D Temporal (CC BY 4.0 / ODbL), the latest year.

Reads the public bucket gs://open-buildings-temporal-data (no account needed), finds the height rasters that cover
the map, and measures each Overture building footprint: median and 90th percentile of the height pixels inside it.
Writes assets/dmp_vysky.json in the format prep.py already uses for laser heights: id -> [median, top].
The rasters are about 4 m effective resolution, so very small buildings get no value and keep izomapa's estimate.

usage: python ci/google_heights.py            (after fetch_data.py; logs band stats so the result can be checked)
"""
import glob, json, math, os, sys, time, urllib.parse, urllib.request
import numpy as np, pyarrow.parquet as pq, shapely
from pyproj import Transformer
import rasterio
from rasterio import features
from rasterio.transform import Affine
import s2sphere

BUCKET = 'open-buildings-temporal-data'
API = f'https://storage.googleapis.com/storage/v1/b/{BUCKET}/o'
YEAR = os.environ.get('OB_YEAR', '2023')
DEC = 4                     # read every 4th pixel of the 0.5 m rasters: 2 m, still finer than the 4 m effective resolution
M = json.load(open('mesto.json'))


def get(url, tries=4):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'izomapa-calicut'}), timeout=120).read()
        except Exception as e:
            if i == tries - 1: raise
            print('retry', url, e, flush=True); time.sleep(3 * (i + 1))


def https(u):
    return 'https://storage.googleapis.com/' + u[5:] if u.startswith('gs://') else u


# --- buildings ---
B = {}
for f in sorted(glob.glob('data*/building.parquet')):
    for r in pq.read_table(f, columns=['id', 'geometry']).to_pylist():
        B.setdefault(r['id'], r['geometry'])
ids = list(B)
geoms = shapely.from_wkb([B[i] for i in ids])
minx, miny, maxx, maxy = shapely.total_bounds(geoms)
print(f'{len(ids)} buildings, bbox {minx:.4f},{miny:.4f} .. {maxx:.4f},{maxy:.4f}', flush=True)

# --- manifests of the S2 level-2 cells covering the bbox ---
tokens = set()
for la in np.linspace(miny, maxy, 5):
    for lo in np.linspace(minx, maxx, 5):
        tokens.add(s2sphere.CellId.from_lat_lng(s2sphere.LatLng.from_degrees(la, lo)).parent(2).to_token())
names = []
for t in sorted(tokens):
    page = None
    while True:
        q = {'prefix': f'v1/manifests/{t}_', 'fields': 'items(name),nextPageToken'}
        if page: q['pageToken'] = page
        d = json.loads(get(API + '?' + urllib.parse.urlencode(q)))
        names += [it['name'] for it in d.get('items', [])]
        page = d.get('nextPageToken')
        if not page: break
print('s2 cells', sorted(tokens), 'manifests', len(names), names[:6], flush=True)
yr = [n for n in names if f'_{YEAR}_' in n] or names
print('using', len(yr), 'manifests for', YEAR, flush=True)

tiles = []
for n in yr:
    man = json.loads(get(f'https://storage.googleapis.com/{BUCKET}/{urllib.parse.quote(n)}'))
    for ts in man['tilesets']:
        crs = ts['crs']; tr = Transformer.from_crs(4326, crs, always_xy=True)
        xs, ys = tr.transform([minx, maxx, minx, maxx], [miny, miny, maxy, maxy])
        box = shapely.box(min(xs), min(ys), max(xs), max(ys))
        for src in ts['sources']:
            a = src['affineTransform']; w, h = src['dimensions']['width'], src['dimensions']['height']
            T = Affine.translation(a['translateX'], a['translateY']) * Affine.scale(a['scaleX'], a['scaleY'])
            poly = shapely.Polygon([T * c for c in [(0, 0), (w, 0), (w, h), (0, h)]])
            if poly.intersects(box):
                tiles.append((https(man['uriPrefix'] + src['uris'][0]), crs))
tiles = sorted(set(tiles))
print('tiles over the map:', len(tiles), flush=True)

# --- measure ---
vals = {}
os.makedirs('build/ob', exist_ok=True)
band_idx = None
for k, (url, crs) in enumerate(tiles):
    fn = f'build/ob/{k}.tif'
    if not os.path.exists(fn): open(fn, 'wb').write(get(url))
    with rasterio.open(fn) as ds:
        if band_idx is None:
            print('bands', ds.count, ds.descriptions, ds.dtypes, 'scales', ds.scales, 'offsets', ds.offsets, 'nodata', ds.nodata, 'res', ds.res, flush=True)
            desc = [(d or '').lower() for d in ds.descriptions]
            band_idx = next((i + 1 for i, d in enumerate(desc) if 'height' in d), None) or int(os.environ.get('OB_BAND', 2))
            print('height band', band_idx, flush=True)
        oh, ow = max(1, ds.height // DEC), max(1, ds.width // DEC)
        arr = ds.read(band_idx, out_shape=(oh, ow)).astype('float32')
        sc = ds.scales[band_idx - 1] or 1; of = ds.offsets[band_idx - 1] or 0
        arr = arr * sc + of
        if ds.nodata is not None: arr[ds.read(band_idx, out_shape=(oh, ow)) == ds.nodata] = np.nan
        T = ds.transform * Affine.scale(ds.width / ow, ds.height / oh)
        tr = Transformer.from_crs(4326, ds.crs, always_xy=True)
        bx = shapely.box(*rasterio.transform.array_bounds(oh, ow, T)[::1])
        g = shapely.transform(geoms, lambda c: np.column_stack(tr.transform(c[:, 0], c[:, 1])))
        hit = np.nonzero(shapely.intersects(g, bx))[0]
        if k == 0 or k == len(tiles) - 1:
            v = arr[np.isfinite(arr)]
            print(f'tile {k}: {ow}x{oh}, values min {v.min():.2f} p50 {np.percentile(v, 50):.2f} p99 {np.percentile(v, 99):.2f} max {v.max():.2f}, buildings {len(hit)}', flush=True)
        if not len(hit): continue
        lab = features.rasterize(((g[i], int(i) + 1) for i in hit), out_shape=(oh, ow), transform=T, fill=0, dtype='int32')
        m = lab > 0
        for i, x in zip(lab[m] - 1, arr[m]):
            if math.isfinite(x): vals.setdefault(int(i), []).append(float(x))
        # buildings too small for a pixel: value at the centroid
        cen = shapely.centroid(g[hit])
        rows, cols = rasterio.transform.rowcol(T, shapely.get_x(cen), shapely.get_y(cen))
        for i, r_, c_ in zip(hit, rows, cols):
            if int(i) not in vals and 0 <= r_ < oh and 0 <= c_ < ow and math.isfinite(arr[r_, c_]):
                vals[int(i)] = [float(arr[r_, c_])]
    os.remove(fn)
    print(f'{k + 1}/{len(tiles)} tiles, {len(vals)} buildings measured', flush=True)

out, hs = {}, []
for i, v in vals.items():
    med = float(np.median(v))
    if med < 2.5 or med > 120: continue                      # ground-level noise or nonsense: keep izomapa's estimate
    out[ids[i]] = [round(med, 1), round(med + 0.6, 1)]      # +0.6: not "flat for sure", roof shape stays izomapa's rule
    hs.append(med)
os.makedirs('assets', exist_ok=True)
json.dump(out, open('assets/dmp_vysky.json', 'w'), separators=(',', ':'))
hs = np.array(hs) if hs else np.array([0.0])
print(f'heights for {len(out)} of {len(ids)} buildings; median {np.median(hs):.1f} m, p90 {np.percentile(hs, 90):.1f} m, max {hs.max():.1f} m;',
      'over 20 m:', int((hs > 20).sum()), 'over 40 m:', int((hs > 40).sum()), flush=True)

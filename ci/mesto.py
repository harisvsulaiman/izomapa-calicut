"""Write mesto.json for Calicut: fixed grid centred on central Kozhikode, terrain zero from Terrarium."""
import io, json, math, urllib.request
import numpy as np
from PIL import Image

LON0, LAT0 = 75.7810, 11.2530          # centre of square (0,0): Mananchira / SM Street / Palayam / beach
# city centre, beach and Kallai river, plus the NH 66 bypass corridor east of the city:
# Malaparamba overpass (1,2), Thondayad flyover (1,1)/(2,1), Palazhi flyover, CyberPark and HiLITE (2,0)/(3,0), towards Pantheerankavu (3,-1)
CELLS = [[0, 2], [1, 2], [0, 1], [1, 1], [2, 1], [0, 0], [1, 0], [2, 0], [3, 0], [0, -1], [1, -1], [2, -1], [3, -1]]
HALF = 1150.0
KX, KY = math.cos(math.radians(LAT0)) * 111320.0, 110574.0
I = [c[0] for c in CELLS]; J = [c[1] for c in CELLS]
lo0, lo1 = LON0 + (min(I) * 2 * HALF - HALF) / KX, LON0 + (max(I) * 2 * HALF + HALF) / KX
la0, la1 = LAT0 + (min(J) * 2 * HALF - HALF) / KY, LAT0 + (max(J) * 2 * HALF + HALF) / KY

def tile(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)

z = 12; hs = []
tx0, ty0 = tile(lo0, la1, z); tx1, ty1 = tile(lo1, la0, z)
for tx in range(tx0, tx1 + 1):
    for ty in range(ty0, ty1 + 1):
        req = urllib.request.Request(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{tx}/{ty}.png', headers={'User-Agent': 'izomapa-calicut'})
        a = np.asarray(Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=60).read())).convert('RGB')).astype(float)
        n = 2 ** z; u = (tx + (np.arange(256) + 0.5) / 256) / n; v = (ty + (np.arange(256) + 0.5) / 256) / n
        lon = u * 360 - 180; lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * v))))
        m = ((lat >= la0) & (lat <= la1))[:, None] & ((lon >= lo0) & (lon <= lo1))[None, :]
        hs.append((a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768)[m])
h = np.concatenate(hs)
href = float(max(0.0, np.percentile(h, 25))); dno = math.floor(float(h.min()) - href - 30)
print(f'terrain {h.min():.0f}..{h.max():.0f} m, zero {href:.1f}, floor {dno}')
mesto = {
    'nazev': 'Calicut', 'zeme': 'in',
    'titulek': 'Isometric Calicut', 'h1': ['Isometric', 'Calicut'],
    'podtitul': 'Calicut (Kozhikode) from open data, in the style of SimCity 2000.',
    'popis': 'An isometric pixel-art map of Calicut (Kozhikode), Kerala, in the style of SimCity 2000. Day and night, weather and the city from open data.',
    'url': 'https://harisvsulaiman.github.io/izomapa-calicut',
    'stred': [LON0, LAT0], 'polovina': HALF, 'ctverce': CELLS, 'rozliseni': 'zakladni',
    'href': round(href, 1), 'dno': dno,
    'mhd': {'gtfs': None, 'zdroj': None, 'zdroj_url': None},
    'vanocni_strom': None, 'letadla': False, 'potoky': False, 'sousedi': [],
    'pocasi': True, 'vitr': True,          # live weather and wind over Calicut from Open-Meteo
}
json.dump(mesto, open('mesto.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# Isometric Calicut

This checkout of izomapa is adapted to build Calicut (Kozhikode, Kerala). The upstream tool is Czech, so here is
what was changed and how to run it.

## Changes from upstream

- `novy_mesto.py` takes `--zeme <country code>` (default `cz`). With anything other than `cz`, the boundary search
  isn't limited to Czechia, the page texts are in English and `mesto.json` gets `"zeme"`.
- `postav.sh` skips the Czech-only data steps (ČÚZK laser heights, orthophoto forest mask, ZABAGED fields) when
  `"zeme"` isn't `cz`. Everything else (Overture buildings, roads, water, land use, Terrarium terrain, OSM
  playgrounds, render, tiles, website) works worldwide.

## Run it (Mac, ideally Apple Silicon with 16 GB)

```sh
./setup.sh
.venv/bin/python novy_mesto.py "Calicut" --zeme in --dotaz "Kozhikode Municipal Corporation, Kerala" --max 4
# check the printed "obec:" line is the corporation (not the whole district) and the square count
./postav.sh            # 30-60 min for 4 squares
.venv/bin/python compose.py summer 8   # build/nahled_summer.png
npm run nahled         # http://localhost:8000
```

`--max 4` builds only the 4 squares (2.3 x 2.3 km each) nearest the centre: Mananchira, SM Street, Palayam and the
beach. Drop `--max` for the whole corporation (about 20-30 squares, several hours, a site of a few GB). You can add
squares later by editing `ctverce` in `mesto.json` and re-running `./postav.sh`.

Or open the folder in Claude Code and say:

> Build the isometric map of Calicut following CALICUT.md. Start with the 4 central squares.

## Known gaps to tune after the first build

- **Seasons:** the viewer has spring/summer/autumn/winter, including snow. For Kerala you'll want to drop winter or
  turn it into a monsoon variant (`render_chunk.sh`, `dzi.py`, `preview.py`, `web/app.html` season buttons).
- **Building heights:** without laser data, heights come from Overture/OSM tags or defaults. Most Calicut
  buildings have no height tags, so expect uniform 1-3 floor guesses. Fix landmarks via `assets/dominanty.json`.
- **Viewer UI language:** `web/app.html` is in Czech (menus, cards, help). It needs translating to English.
- **Landmarks** for `assets/dominanty.json`: Mananchira Square, Kuttichira Mishkal Mosque, Tali Temple, Calicut
  lighthouse and beach, Kozhikode railway station, HiLITE Mall. Build them from your own photos.
- **Credits:** `build_html.py` lists geoportal.cuzk.cz as a data source. Remove it for a non-Czech map, but keep the
  OpenStreetMap/Overture credits and the izomapa author credit.
- **Public transport:** KSRTC and private buses have no public GTFS, so leave `mhd` empty.

import json
import struct
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STL_PATH = sys.argv[1] if len(sys.argv) > 1 else "verktyg/ottfjallet.stl"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "bilder/terrain.js"

# --- Las in binar STL -------------------------------------------------------
with open(STL_PATH, "rb") as f:
    f.read(80)
    tricount = struct.unpack("<I", f.read(4))[0]
    tris = np.zeros((tricount, 3, 3), dtype=np.float64)
    for i in range(tricount):
        data = f.read(50)
        vals = struct.unpack("<12fH", data)
        tris[i, 0] = vals[3:6]
        tris[i, 1] = vals[6:9]
        tris[i, 2] = vals[9:12]

verts = tris.reshape(-1, 3)
uniq = np.unique(verts.round(decimals=4), axis=0)

# --- Bygg om till ett regelbundet hojdraster (full uplosning) ---------------
# Modellen ar en fysisk (3D-utskriftsbar) klump med platt botten/sidor -
# vi vill bara ha toppytan (terrangen), sa vi tar max Z per (X,Y)-position.
xs = np.unique(np.round(uniq[:, 0], 2))
ys = np.unique(np.round(uniq[:, 1], 2))
xi_idx = {v: i for i, v in enumerate(xs)}
yi_idx = {v: i for i, v in enumerate(ys)}

grid = np.zeros((len(ys), len(xs)), dtype=np.float64)
xr = np.round(uniq[:, 0], 2)
yr = np.round(uniq[:, 1], 2)
zr = uniq[:, 2]
for k in range(len(uniq)):
    xi = xi_idx[xr[k]]
    yi = yi_idx[yr[k]]
    if zr[k] > grid[yi, xi]:
        grid[yi, xi] = zr[k]

# --- Skala om till scenens varldsenheter --------------------------------
half_x = (xs.max() - xs.min()) / 2.0
half_y = (ys.max() - ys.min()) / 2.0
xy_scale = 1.75 / max(half_x, half_y)
cx = (xs.max() + xs.min()) / 2.0
cy = (ys.max() + ys.min()) / 2.0

zmin = grid.min()
zmax = grid.max()
z_scale = 1.05 / (zmax - zmin)

# --- Waterline-konturer direkt fran den riktiga hojddatan --------------
# Samma princip som CNC-strategin "Waterline" - tata, horisontella
# konstant-Z-linjer som foljer terrangen, utan retracts/rapids/stock.
X, Y = np.meshgrid(xs, ys)
NLEV = 46
levels = np.linspace(zmin + (zmax - zmin) * 0.012, zmax - (zmax - zmin) * 0.004, NLEV)

fig, ax = plt.subplots()
cs = ax.contour(X, Y, grid, levels=levels)
out_rings = []
for i, lev in enumerate(levels):
    for seg in cs.allsegs[i]:
        if len(seg) < 6:
            continue
        d = np.sqrt(((seg[1:] - seg[:-1]) ** 2).sum(axis=1))
        s = np.concatenate([[0.0], np.cumsum(d)])
        if s[-1] < 50.0:
            continue
        m = int(np.clip(s[-1] / 1.7, 20, 260))
        si = np.linspace(0, s[-1], m)
        pts = np.stack([np.interp(si, s, seg[:, 0]), np.interp(si, s, seg[:, 1])], axis=1)
        z = round(float((lev - zmin) * z_scale), 4)
        flat = []
        for x, y in pts:
            flat.append(round(float((x - cx) * xy_scale), 3))
            flat.append(round(float((y - cy) * xy_scale), 3))
        out_rings.append({"z": z, "pts": flat})
plt.close(fig)

data = {
    "rings": out_rings,
    "levelCount": NLEV,
    "peak": round(float((zmax - zmin) * z_scale), 4),
}

js = "var TERRAIN_RINGS = " + json.dumps(data, separators=(",", ":")) + ";\n"
with open(OUT_PATH, "w") as f:
    f.write(js)

print("ringar:", len(out_rings), "punkter:", sum(len(r["pts"]) // 2 for r in out_rings), "bytes:", len(js))

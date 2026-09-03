import json
import struct
import sys
import numpy as np

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

# --- Bygg om till ett regelbundet hojdraster ---------------------------
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

# --- Nervaxling for webben ---------------------------------------------
STRIDE = 3
g = grid[::STRIDE, ::STRIDE]
xs_d = xs[::STRIDE]
ys_d = ys[::STRIDE]
rows, cols = g.shape

# --- Skala om till scenens varldsenheter --------------------------------
half_x = (xs_d.max() - xs_d.min()) / 2.0
half_y = (ys_d.max() - ys_d.min()) / 2.0
xy_scale = 1.75 / max(half_x, half_y)
world_half_x = half_x * xy_scale
world_half_z = half_y * xy_scale

zmin = g.min()
zmax = g.max()
z_scale = 1.05 / (zmax - zmin)

heights = ((g - zmin) * z_scale)

data = {
    "rows": rows,
    "cols": cols,
    "halfX": round(float(world_half_x), 4),
    "halfZ": round(float(world_half_z), 4),
    "peak": round(float(heights.max()), 4),
    "heights": [round(float(v), 4) for v in heights.flatten()],
}

js = "var TERRAIN_MESH = " + json.dumps(data, separators=(",", ":")) + ";\n"
with open(OUT_PATH, "w") as f:
    f.write(js)

print("rows", rows, "cols", cols, "verts", rows * cols, "tris", 2 * (rows - 1) * (cols - 1),
      "halfX", world_half_x, "halfZ", world_half_z, "peak", heights.max(), "bytes", len(js))

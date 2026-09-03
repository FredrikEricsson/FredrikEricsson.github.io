import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Samma hojdfalt som verktyg/gen_waterline.py (identisk formel) - sa 3D-modellen
# blir precis samma "Ottfjallet"-form som den tidigare platta konturbilden.
N = 900
L = 1.75
xs = np.linspace(-L, L, N)
ys = np.linspace(-L, L, N)
X, Y = np.meshgrid(xs, ys)


def g(cx, cy, sx, sy, rot=0.0):
    c, s = np.cos(rot), np.sin(rot)
    u = (X - cx) * c + (Y - cy) * s
    v = -(X - cx) * s + (Y - cy) * c
    return np.exp(-(u**2 / sx + v**2 / sy))


H = (1.34 * g(-0.42, -0.30, 1.05, 0.52, 0.62)
     + 0.98 * g( 0.58,  0.48, 0.52, 0.95, -0.34)
     + 0.60 * g( 0.02, -0.92, 0.34, 0.27, 0.15)
     + 0.34 * g(-1.02,  0.62, 0.24, 0.34, 0.0)
     - 0.88 * g( 0.06, -0.04, 0.21, 0.31, 0.75)
     - 0.34 * g(-0.78,  0.48, 0.17, 0.21, 0.0)
     - 0.22 * g( 0.92, -0.55, 0.20, 0.16, 0.4))

H += 0.14 * X * Y * np.exp(-(X**2 + Y**2) / 3.0)

R = np.sqrt((X / 1.55)**2 + (Y / 1.55)**2)
H *= np.clip(1.0 - np.exp(6.0 * (R - 1.0)), 0.0, 1.0)
H = np.maximum(H, 0.0)
H = H.max() * (H / H.max()) ** 0.72

hmax = H.max()
NLEV = 42
levels = np.linspace(hmax * 0.010, hmax * 0.996, NLEV)

fig, ax = plt.subplots()
cs = ax.contour(X, Y, H, levels=levels)
rings = []
for i, lev in enumerate(levels):
    for seg in cs.allsegs[i]:
        if len(seg) < 8:
            continue
        d = np.sqrt(((seg[1:] - seg[:-1]) ** 2).sum(axis=1))
        s = np.concatenate([[0.0], np.cumsum(d)])
        if s[-1] < 0.05:
            continue
        m = int(np.clip(s[-1] / 0.03, 16, 220))
        si = np.linspace(0, s[-1], m)
        pts = np.stack([np.interp(si, s, seg[:, 0]), np.interp(si, s, seg[:, 1])], axis=1)
        rings.append((float(lev), pts))
plt.close(fig)

ZSCALE = 1.05 / hmax

out_rings = []
for lev, pts in rings:
    z = round(float(lev) * ZSCALE, 4)
    flat = []
    for x, y in pts:
        flat.append(round(float(x), 3))
        flat.append(round(float(y), 3))
    out_rings.append({"z": z, "pts": flat})

data = {
    "rings": out_rings,
    "levelCount": NLEV,
}

js = "var TERRAIN_RINGS = " + json.dumps(data, separators=(",", ":")) + ";\n"
with open("bilder/terrain.js", "w") as f:
    f.write(js)

print("ringar:", len(out_rings), "punkter totalt:", sum(len(r["pts"]) // 2 for r in out_rings), "bytes:", len(js))

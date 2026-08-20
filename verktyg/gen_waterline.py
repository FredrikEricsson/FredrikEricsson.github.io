import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
H = H.max() * (H / H.max()) ** 0.72          # plana toppar -> skalform, inte berg

hmax = H.max()
NLEV = 58
levels = np.linspace(hmax * 0.010, hmax * 0.996, NLEV)

fig, ax = plt.subplots()
cs = ax.contour(X, Y, H, levels=levels)
world = []
for i, lev in enumerate(levels):
    for seg in cs.allsegs[i]:
        if len(seg) < 8:
            continue
        closed = abs(seg[0, 0] - seg[-1, 0]) < 1e-9 and abs(seg[0, 1] - seg[-1, 1]) < 1e-9
        d = np.sqrt(((seg[1:] - seg[:-1])**2).sum(axis=1))
        s = np.concatenate([[0.0], np.cumsum(d)])
        if s[-1] < 0.05:
            continue
        m = int(np.clip(s[-1] / 0.012, 40, 900))
        si = np.linspace(0, s[-1], m)
        pts = np.stack([np.interp(si, s, seg[:, 0]), np.interp(si, s, seg[:, 1])], axis=1)
        world.append((i, pts, closed))
plt.close(fig)

ISO_C, ISO_S = np.cos(np.pi / 6), np.sin(np.pi / 6)
ZS = 0.98
K = 2.0 * ISO_S / ZS


def sampleH(qx, qy):
    fx = (qx + L) / (2 * L) * (N - 1)
    fy = (qy + L) / (2 * L) * (N - 1)
    inside = (fx >= 0) & (fx <= N - 1) & (fy >= 0) & (fy <= N - 1)
    fxc = np.clip(fx, 0, N - 1.001)
    fyc = np.clip(fy, 0, N - 1.001)
    x0 = fxc.astype(np.int32); y0 = fyc.astype(np.int32)
    tx = fxc - x0; ty = fyc - y0
    h = (H[y0, x0] * (1 - tx) * (1 - ty) + H[y0, x0 + 1] * tx * (1 - ty)
         + H[y0 + 1, x0] * (1 - tx) * ty + H[y0 + 1, x0 + 1] * tx * ty)
    return np.where(inside, h, 0.0)


lens = [len(p) for _, p, _ in world]
allpts = np.concatenate([p for _, p, _ in world], axis=0)
allz = np.concatenate([np.full(len(p), levels[i]) for i, p, _ in world])
hidden = np.zeros(len(allpts), dtype=bool)
for t in np.arange(0.02, 3.6, 0.018):
    hq = sampleH(allpts[:, 0] + t, allpts[:, 1] + t)
    hidden |= hq > allz + t * K + 0.004
vis = ~hidden

px = (allpts[:, 0] - allpts[:, 1]) * ISO_C
py = (allpts[:, 0] + allpts[:, 1]) * ISO_S - allz * ZS
proj = np.stack([px, py], axis=1) * 100.0

segments = []
off = 0
for (i, p, closed), n in zip(world, lens):
    pp = proj[off:off + n]
    vv = vis[off:off + n]
    off += n
    if closed and vv.any() and (~vv).any():
        r = int(np.argmax(~vv))
        pp = np.roll(pp, -r, axis=0)
        vv = np.roll(vv, -r)
    run = []
    for pt, v in zip(pp, vv):
        if v:
            run.append(pt)
        elif run:
            if len(run) > 1:
                segments.append((i, np.array(run)))
            run = []
    if len(run) > 1:
        segments.append((i, np.array(run)))

xall = np.concatenate([s[:, 0] for _, s in segments])
yall = np.concatenate([s[:, 1] for _, s in segments])
x0, x1, y0, y1 = xall.min(), xall.max(), yall.min(), yall.max()
pad = 0.03 * max(x1 - x0, y1 - y0)
scale = max(x1 - x0, y1 - y0)
vb = f"{x0-pad:.1f} {y0-pad:.1f} {x1-x0+2*pad:.1f} {y1-y0+2*pad:.1f}"

out = [f'<svg viewBox="{vb}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">',
       '  <g fill="none" stroke="#c9a227" stroke-linecap="round" stroke-linejoin="round">']
for i, s in segments:
    t = i / (NLEV - 1)
    op = 0.32 + 0.62 * (t ** 0.8)
    sw = scale * (0.00105 if i % 9 else 0.0018)
    s2 = s[::2] if len(s) > 60 else s
    if len(s2) < 2:
        s2 = s
    d = "M " + " L ".join(f"{a:.0f} {b:.0f}" for a, b in s2)
    out.append(f'    <path d="{d}" stroke-width="{sw:.3f}" opacity="{op:.3f}"/>')
out.append('  </g>')
out.append('</svg>')
svg = "\n".join(out)
open("waterline.svg", "w").write(svg)
print("segment:", len(segments), "bytes:", len(svg), "viewBox:", vb)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汉/唐影带改版为宋式口径（tools/restyle_band_song.py）

背景：build_tang_geom.compute_eclipse 生成的
  · umbraPolygon   = 全程扫过走廊（band_edges_from_contours，跨度 30–100°）
  · penumbraPolygon = 接触相位逐时刻轮廓并集包络（可被撑到 145–360°）
与宋版（data/song.js）的样式不一致：宋的多边形是【食甚时刻的瞬时地表落区】——
  · 本影/伪本影：mc=1 等值线（跨度约 1–3°）
  · 半影：mp=0 等值线（地面直径约 70–90°）
  · 扫过过程由中心线 + 逐帧影心回放（shadowFrames）呈现。

本脚本对 data/han.js 与 data/tang.js 逐条复算【食甚时刻瞬时轮廓】并替换两个
多边形字段；其余字段（中心线/逐帧/观测点/时间轴/官方校验值）一律不动。
锚定：maxEclipse(UTC ISO) + extra.cat.dt（官方目录逐条 ΔT）→ JD(TT)；
缺 cat.dt 时退回 Espenak & Meeus 多项式。
"""
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tang_geom as tg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ISO_RE = re.compile(r'^(-?\d+)-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$')


def iso_to_jd_ut(iso):
    """iso_utc 的逆变换（儒略历日期 + UTC 时刻 → JD(UT)，含 6 位 BC 年）。"""
    m = ISO_RE.match(iso)
    if not m:
        return None
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    return tg.jdn_julian(y, mo, d) - 0.5 + (hh * 3600 + mm * 60 + ss) / 86400.0


def contour_to_flat(P):
    """ECEF 轮廓环 → 扁平 [lon,lat,...]，经度连续化展开（不回卷 ±180）。"""
    pts = []
    prev = None
    for q in P:
        lat, lon = tg.ecef_to_latlon(q)
        if prev is not None:
            while lon - prev > 180: lon -= 360.0
            while lon - prev < -180: lon += 360.0
        pts.append([lon, lat])
        prev = lon
    return pts


def flat_ok(pts, min_pts=8):
    return len(pts) >= min_pts


def restyle_file(path, key):
    src = open(path, encoding='utf-8').read()
    j = src.index('=', src.index('.' + key))
    head = src[:j + 1]
    obj = json.loads(src[j + 1:].strip().rstrip(';'))
    n_u = n_p = n_skip = 0
    stats_u, stats_p = [], []
    for rec in obj['records']:
        tr = rec.get('timeRange') or {}
        if not tr.get('maxEclipse'):
            n_skip += 1
            continue
        e = rec.get('extra') or {}
        cat = e.get('cat') or {}
        dt_s = cat.get('dt') or tg.dt_for_jd(iso_to_jd_ut(tr['maxEclipse']) - 0.5)
        jd_ut = iso_to_jd_ut(tr['maxEclipse'])
        jd_tt = jd_ut + dt_s / 86400.0
        S, M = tg.sun_moon_ecef(jd_tt, jd_ut)

        # 食甚时刻影轴足点（偏食时轴不触地 → 最近地表点）
        axis = tg.axis_footprint(S, M)
        center = axis if axis is not None else tg.closest_surface_point(S, M)

        # 半影：mp=0 瞬时等值线（与宋同口径）
        Pp = tg.trace_contour(S, M, center, False, nrays=48)
        pen = contour_to_flat(Pp) if len(Pp) else []
        rec['penumbraPolygon'] = [round(v, 3) for p in pen for v in p] if flat_ok(pen) else []
        if rec['penumbraPolygon']:
            n_p += 1
            lons = rec['penumbraPolygon'][0::2]; lats = rec['penumbraPolygon'][1::2]
            stats_p.append((max(lons) - min(lons), max(lats) - min(lats)))

        # 本影/伪本影：mc=1 瞬时等值线；仅中心食（偏食无，与宋一致）
        umb = []
        if rec.get('centralLine') and len(rec['centralLine']) > 1 and axis is not None:
            Pu = tg.trace_contour(S, M, axis, True, nrays=48)
            umb = contour_to_flat(Pu) if len(Pu) else []
        rec['umbraPolygon'] = [round(v, 3) for p in umb for v in p] if flat_ok(umb) else []
        if rec['umbraPolygon']:
            n_u += 1
            lons = rec['umbraPolygon'][0::2]; lats = rec['umbraPolygon'][1::2]
            stats_u.append((max(lons) - min(lons), max(lats) - min(lats)))

    with open(path, 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print(f"[{key}] 瞬时本影 {n_u} 条 / 瞬时半影 {n_p} 条 / 无几何跳过 {n_skip} 条")
    if stats_u:
        import statistics as st
        print(f"  本影跨度 dLon 中位 {st.median(x[0] for x in stats_u):.1f}°（宋口径 1–3°）")
    if stats_p:
        import statistics as st
        print(f"  半影直径 中位 {st.median((x[0]+x[1])/2 for x in stats_p):.1f}°（宋口径 ~70–90°）")


def run():
    for path, key in ((os.path.join(ROOT, 'data/han.js'), 'han'),
                      (os.path.join(ROOT, 'data/tang.js'), 'tang')):
        restyle_file(path, key)


if __name__ == '__main__':
    run()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唐代日食星历复算引擎（tools/build_tang_geom.py）

把 data/tang.js 从「点位降级示意」升级为「真实复算几何」：
  历朔干支匹配精确朔时刻 → 中心线 / 本影带 / 半影区 / 逐帧影心 / 观测点实况。

方法（严格矢量影锥几何，非经典 Besselian 公式表）：
  - PyEphem（ELP2000/VSOP 截断级数）给日、月地心视位置（g_ra/g_dec，日期分点）；
  - 任意地表点 P 的遮挡判定直接用定义：日月角距 sep 与半径 rs/rm 比较——
      偏食区 mp=(rs+rm−sep)/(2rs)>0；中心区 mc=(rs+rm−sep)/(2·min(rs,rm))≥1。
    与影锥/椭球相交在数学上等价，且免去经典公式换算的符号陷阱；
  - 影轴足点：影轴线（过月心、方向 v̂=M−S）与 WGS84 椭球解析求交；
  - 影带多边形：逐时刻沿 72 方位射线在切平面二分求等值线，再做
    并集包络过滤（保留不被其他时刻区域吞没的边界点）合成扫过带；
  - ΔT：Espenak & Meeus 2006 五千年宝典分段多项式。

验证（--validate）：
  1) 2024-04-08 现代日食（中心线应横贯墨西哥→北美）；
  2) 960-05-28 与宋存量几何（song.js 0001 环食）互校；
  3) 全量运行后与《新唐书》「既／几既／不尽如钩」原文食型词互证。
"""
import json, math, sys, os
import numpy as np
import ephem
from pymeeus.Moon import Moon as _PmMoon
from pymeeus.Sun import Sun as _PmSun
from pymeeus.Epoch import Epoch as _PmEpoch

AU = 1.495978707e8
A_EQ = 6378.137          # WGS84 赤道半径 km
B_PO = 6356.7523         # 极半径 km
E2 = 1 - B_PO ** 2 / A_EQ ** 2
R_SUN = 696000.0
R_MOON = 1737.4
JD_OFFSET = 2415020.0    # PyEphem 日期数 = JD − offset

GAN = '甲乙丙丁戊己庚辛壬癸'
ZHI = '子丑寅卯辰巳午未申酉戌亥'
CHANGAN_LON = 108.94
LMT_H = CHANGAN_LON / 15.0   # 长安地方时 = UTC + 7.26h

STATIONS = [
    {"name": "长安", "lon": 108.94, "lat": 34.27},
    {"name": "洛阳", "lon": 112.45, "lat": 34.62},
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- 时间 / 历日

def delta_t(y):
    """Espenak & Meeus 2006 分段多项式（秒）。y 可为小数年。"""
    if y < -500:
        u = (y - 1820) / 100.0
        return -20 + 32 * u * u
    if y < 500:
        u = y / 100.0
        return (10583.6 - 1014.41 * u + 33.78311 * u ** 2 - 5.952053 * u ** 3
                - 0.1798452 * u ** 4 + 0.022174192 * u ** 5 + 0.0090316521 * u ** 6)
    if y < 1600:
        u = (y - 1000) / 100.0
        return (1574.2 - 556.01 * u + 71.23472 * u ** 2 + 0.319781 * u ** 3
                - 0.8503463 * u ** 4 - 0.005050998 * u ** 5 + 0.0083572073 * u ** 6)
    if y < 1700:
        t = y - 1600
        return 120 - 0.9808 * t - 0.01532 * t ** 2 + t ** 3 / 7129.0
    if y < 1800:
        t = y - 1700
        return 8.83 + 0.1603 * t - 0.0059285 * t ** 2 + 0.00013336 * t ** 3 - t ** 4 / 1174000.0
    if y < 1900:
        t = y - 1800
        return 13.72 - 0.332447 * t + 0.0068637 * t ** 2 + 0.004111 * t ** 3 - 0.00037436 * t ** 4
    if y < 2005:
        t = y - 1900
        return (-2.79 + 1.494119 * t - 0.0598939 * t ** 2 + 0.0061966 * t ** 3
                - 0.000197 * t ** 4)
    u = (y - 1820) / 100.0
    return -20 + 32 * u * u


def jdn_julian(y, m, d):
    a = (14 - m) // 12; yy = y + 4800 - a; mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - 32083


def jdn_to_julian(j):
    c = j + 32082; dd = (4 * c + 3) // 1461; e = c - (1461 * dd) // 4; m = (5 * e + 2) // 153
    return (dd - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1)


def ganzhi(j):
    i = (j + 49) % 60
    return GAN[i % 10] + ZHI[i % 12]


def jd_ut_to_civil(jd_ut):
    jdn = int(math.floor(jd_ut + 0.5))
    frac = jd_ut + 0.5 - jdn
    y, m, d = jdn_to_julian(jdn)
    return y, m, d, frac * 86400.0


def iso_utc(jd_ut):
    """与宋数据同口径：Julian 历日期 + UTC 时刻 + Z（4 位年）。"""
    y, m, d, sec = jd_ut_to_civil(jd_ut)
    secs = int(round(sec))
    if secs >= 86400:
        secs -= 86400
        y, m, d = jdn_to_julian(int(math.floor(jd_ut + 0.5)) + 1)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, m, d, secs // 3600, secs % 3600 // 60, secs % 60)


def date_label_from_jdn(jdn):
    y, m, d = jdn_to_julian(jdn)
    return "%04d-%02d-%02d" % (y, m, d)


def dt_for_jd(jd_ut):
    y, _, _, _ = jd_ut_to_civil(jd_ut)
    return delta_t(float(y))


# ---------------------------------------------------------------- 天体与几何

def eph_date(jd):
    return ephem.Date(jd - JD_OFFSET)


_GAST_OBS = None
def gast(jd_ut):
    global _GAST_OBS
    if _GAST_OBS is None:
        _GAST_OBS = ephem.Observer()
        _GAST_OBS.lon = '0'; _GAST_OBS.lat = '0'; _GAST_OBS.elevation = 0
    _GAST_OBS.date = eph_date(jd_ut)
    return float(_GAST_OBS.sidereal_time())


def _to_ecef(body, g):
    ra = float(body.g_ra); dec = float(body.g_dec)
    dist = float(body.earth_distance) * AU
    v = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]) * dist
    cg, sg = math.cos(g), math.sin(g)
    return np.array([cg * v[0] + sg * v[1], -sg * v[0] + cg * v[1], v[2]])


def obliquity_deg(jd):
    """黄赤交角（IAU 多项式，度）。公元前年代 ≈23.7°，不可用现代常数。"""
    T = (jd - 2451545.0) / 36525.0
    return 23.43929111 - (46.8150 * T + 0.00059 * T ** 2 - 0.001813 * T ** 3) / 3600.0


def _pm_ecef(lam, bet, dist, eps_r, cg, sg):
    """黄道(分点)坐标 → 地固 ECEF（km）。lam/bet 度，dist km。"""
    lam_r, bet_r = math.radians(float(lam)), math.radians(float(bet))
    x = dist * math.cos(bet_r) * math.cos(lam_r)
    y = dist * math.cos(bet_r) * math.sin(lam_r)
    z = dist * math.sin(bet_r)
    ye = y * math.cos(eps_r) - z * math.sin(eps_r)
    ze = y * math.sin(eps_r) + z * math.cos(eps_r)
    return np.array([cg * x + sg * ye, -sg * x + cg * ye, ze])


def sun_moon_ecef(jd_tt, jd_ut):
    """日、月 ECEF（km）。星历层用 pymeeus（Meeus ELP-2000/82 + VSOP87 全项）：
    pyephem 的截断月历在古代年代有系统性黄经偏差（BC 204 约 1.8°≈3.5h，
    唐 600-900 年代约 0.3°≈35min），会导致食甚时刻偏早与影带东西平移；
    pymeeus 与 NASA 五千年谱（VSOP87 + ELP2000-82）同为 ELP 理论族，
    经官方目录逐条锚定验证（-204-12-20：mag 0.85/0.8464、TD 精确命中）。
    gast 仍用 ephem（已对照 IAU GMST 解析式验证至 0.004°）。
    注意：jd_tt 为 TT，jd_ut = jd_tt − ΔT（地球自转角用 UT）。"""
    ep = _PmEpoch(jd_tt)
    lam_m, bet_m, dist_km, _ppi = _PmMoon.geocentric_ecliptical_pos(ep)
    lam_s, bet_s, R_au = _PmSun.apparent_geocentric_position(ep)
    eps_r = math.radians(obliquity_deg(jd_tt))
    g = gast(jd_ut)                       # 弧度，勿再 radians()
    cg, sg = math.cos(g), math.sin(g)
    S = _pm_ecef(lam_s, bet_s, float(R_au) * AU, eps_r, cg, sg)
    M = _pm_ecef(lam_m, bet_m, float(dist_km), eps_r, cg, sg)
    return S, M


def surface_ecef(lat, lon):
    la = math.radians(lat); lo = math.radians(lon)
    N = A_EQ / math.sqrt(1 - E2 * math.sin(la) ** 2)
    return np.array([N * math.cos(la) * math.cos(lo),
                     N * math.cos(la) * math.sin(lo),
                     N * (1 - E2) * math.sin(la)])


def ecef_to_latlon(P):
    x, y, z = P
    p = math.hypot(x, y)
    lat = math.atan2(z, p)
    for _ in range(4):
        N = A_EQ / math.sqrt(1 - E2 * math.sin(lat) ** 2)
        lat = math.atan2(z, p - E2 * N * math.sin(lat))
    return math.degrees(lat), math.degrees(math.atan2(y, x))


def ray_surface(d):
    t = 1.0 / math.sqrt((d[0] ** 2 + d[1] ** 2) / A_EQ ** 2 + d[2] ** 2 / B_PO ** 2)
    return t * d


def surface_normal(P):
    n = np.array([P[0] / A_EQ ** 2, P[1] / A_EQ ** 2, P[2] / B_PO ** 2])
    return n / np.linalg.norm(n)


def sun_alt(P, S):
    n = surface_normal(P)
    Su = S - P
    return 90.0 - math.degrees(math.acos(np.clip(np.dot(Su, n) / np.linalg.norm(Su), -1, 1)))


def mags(Ps, S, M):
    """向量化：Ps (N,3) 地表点 ECEF km → (偏食mag, 中心mag, rs, rm, sep)。"""
    Su = S[None, :] - Ps
    Mo = M[None, :] - Ps
    n1 = np.linalg.norm(Su, axis=1); n2 = np.linalg.norm(Mo, axis=1)
    rs = np.arcsin(R_SUN / n1)
    rm = np.arcsin(R_MOON / n2)
    cs = np.einsum('ij,ij->i', Su, Mo) / (n1 * n2)
    sep = np.arccos(np.clip(cs, -1.0, 1.0))
    mp = (rs + rm - sep) / (2 * rs)
    mc = (rs + rm - sep) / (2 * np.minimum(rs, rm))
    return mp, mc, rs, rm, sep


def mag_at(P, S, M):
    mp, mc, rs, rm, sep = mags(np.asarray(P)[None, :], S, M)
    return float(mp[0]), float(mc[0]), float(rs[0]), float(rm[0]), float(sep[0])


def axis_footprint(S, M):
    """影轴线（过月心、方向 v̂=M−S）与椭球交点，取离月心近者；不相交返回 None。"""
    v = M - S
    v = v / np.linalg.norm(v)
    a = (v[0] ** 2 + v[1] ** 2) / A_EQ ** 2 + v[2] ** 2 / B_PO ** 2
    b = (M[0] * v[0] + M[1] * v[1]) / A_EQ ** 2 + M[2] * v[2] / B_PO ** 2
    c = (M[0] ** 2 + M[1] ** 2) / A_EQ ** 2 + M[2] ** 2 / B_PO ** 2
    disc = b * b - a * (c - 1.0)
    if disc < 0:
        return None
    r = math.sqrt(disc)
    cands = [M + s * v for s in ((-b - r) / a, (-b + r) / a)]
    return min(cands, key=lambda P: np.linalg.norm(P - M))


def closest_surface_point(S, M):
    """影轴未触地（偏食）时：轴离地心最近方向的地表点（最大食分点近似）。"""
    v = M - S
    v /= np.linalg.norm(v)
    n = M - float(np.dot(M, v)) * v
    return ray_surface(n / np.linalg.norm(n))


# ---------------------------------------------------------------- 等值线与包络

def trace_contour(S, M, center, umbra, nrays=72, smax_deg=None):
    """以 center 为切点的 gnomonic 平面上沿方位射线二分求等值线。
    umbra=True → mc=1（本影/伪本影边界）；False → mp=0（半影边界）。返回 (N,3)。"""
    gh = np.asarray(center, float)
    gh = gh / np.linalg.norm(gh)
    z = np.array([0, 0, 1.0])
    e1 = np.cross(z, gh)
    if np.linalg.norm(e1) < 1e-9:
        e1 = np.array([1.0, 0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(gh, e1)
    th = np.linspace(0, 2 * math.pi, nrays, endpoint=False)
    dirs = np.outer(np.cos(th), e1) + np.outer(np.sin(th), e2)
    hi0 = math.radians(smax_deg if smax_deg else (3.2 if umbra else 55.0))

    def value(s_arr):
        d = gh[None, :] + dirs * s_arr[:, None]
        d /= np.linalg.norm(d, axis=1)[:, None]
        P = d * (1.0 / np.sqrt((d[:, 0] ** 2 + d[:, 1] ** 2) / A_EQ ** 2
                               + d[:, 2] ** 2 / B_PO ** 2))[:, None]
        mp, mc, _, _, _ = mags(P, S, M)
        return P, (mc - 1.0) if umbra else mp

    lo = np.zeros(nrays)
    hi = np.full(nrays, hi0)
    _, vh = value(hi)
    valid = vh < 0
    if not valid.any():
        return np.zeros((0, 3))
    for _ in range(42):
        mid = (lo + hi) / 2
        _, vm = value(mid)
        inside = vm > 0
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    s_root = (lo + hi) / 2
    P, _ = value(s_root)
    return P[valid]


def region_inside_pre(Ps, SS, MM, umbra, exclude_idx=None):
    """Ps 是否落在任一预计算时刻的区域内（纯 numpy，ephem 已预取）。
    umbra=True 用 mc≥1（留 1e-4 容差），否则 mp>0（留 1e-4 容差）。"""
    res = np.zeros(len(Ps), bool)
    thr = 1.0 - 1e-4
    for j in range(len(SS)):
        if j == exclude_idx:
            continue
        mp, mc, _, _, _ = mags(Ps, SS[j], MM[j])
        res |= (mc >= thr) if umbra else (mp > 1e-4)
    return res


def polygon_from_envelope(env, track, SS, MM, umbra):
    """并集包络过滤（排除自身时刻）+ N/S 分侧排序 → 扁平 [lon,lat,...]。
    env: [(k, P(N,3))]（k 为时间档序号）；track: [(lon,lat)] 中心轨迹（定方向）。"""
    if len(env) < 2:
        return []
    flat_pts = []
    for k, P in env:
        if not len(P):
            continue
        keep = ~region_inside_pre(P, SS, MM, umbra, exclude_idx=k)
        for q in P[keep]:
            lat, lon = ecef_to_latlon(q)
            flat_pts.append((k, lon, lat))
    if len(flat_pts) < 8:
        return []
    ax = track[-1][0] - track[0][0]; ay = track[-1][1] - track[0][1]
    nrm = math.hypot(ax, ay)
    if nrm < 1e-9:
        return []
    ax /= nrm; ay /= nrm
    mid = track[len(track) // 2]
    sides = []
    for (k, lon, lat) in flat_pts:
        cross = ax * (lat - mid[1]) - ay * (lon - mid[0])
        sides.append((k, lon, lat, 1 if cross >= 0 else -1))
    sideA = sorted([p for p in sides if p[3] > 0], key=lambda p: p[0])
    sideB = sorted([p for p in sides if p[3] < 0], key=lambda p: p[0])
    if len(sideA) < 3 or len(sideB) < 3:
        poly = sorted(sides, key=lambda p: p[0])
    else:
        poly = sideA + list(reversed(sideB))
    out = []
    for p in poly:
        out.extend([round(p[1], 3), round(p[2], 3)])
    return out


def _medianfilt(seq, w=5):
    """窗口中位数滤波（边界收缩）。"""
    n = len(seq); h = w // 2
    out = []
    for i in range(n):
        lo = max(0, i - h); hi = min(n, i + h + 1)
        out.append(float(np.median(seq[lo:hi])))
    return out


def band_edges_from_contours(raw, cap_km=350.0):
    """本影带多边形：逐时刻取本影轮廓在轨迹垂向上的极值偏移（标量，km），
    经中位数滤波后叠加回平滑的影心轨迹 → 左右两条边链 → up + reversed(dn)。
    相比直接用极值点：宽度序列滤波可消除掠地细长条造成的首段跳动与内部尖刺；
    相比 buffer_band：无曲线路径自交；经度连续化展开，不回卷到 ±180；
    极区（|lat|→90）做跨极换算。"""
    cent, ru, rd, pes, pns, lats = [], [], [], [], [], []
    for i, (m, lon, lat, fp, Pu) in enumerate(raw):
        if not len(Pu):
            continue
        j0 = max(0, i - 1); j1 = min(len(raw) - 1, i + 1)
        dlon = raw[j1][1] - raw[j0][1]
        dlat = raw[j1][2] - raw[j0][2]
        latm = math.radians((raw[j0][2] + raw[j1][2]) / 2)
        e = dlon * math.cos(latm); nn = dlat
        L = math.hypot(e, nn)
        if L < 1e-12:
            e, nn = 1.0, 0.0
        else:
            e /= L; nn /= L
        pe, pn = nn, -e                       # 与 perp_radius 同口径
        xs = np.array([ecef_to_latlon(p)[1] for p in Pu])
        ys = np.array([ecef_to_latlon(p)[0] for p in Pu])
        proj = ((xs - lon) * 111.32 * math.cos(latm) * pe
                + (ys - lat) * 111.32 * pn)
        if np.max(np.abs(proj)) > cap_km:     # 轮廓病态（如掠地时局部畸变）→ 弃该时刻
            continue
        cent.append((lon, lat)); pes.append(pe); pns.append(pn); lats.append(latm)
        ru.append(float(np.max(proj))); rd.append(float(np.min(proj)))

    if len(cent) < 3:
        return []
    ru = np.array(_medianfilt(ru, 5))
    rd = np.array(_medianfilt(rd, 5))
    # 端部渐缩成尖（掠地起止），并压掉端部残余不稳
    k = min(3, len(cent) // 3)
    for arr in (ru, rd):
        for j in range(k):
            f = (j + 1) / (k + 1)
            arr[j] *= f; arr[-1 - j] *= f

    def build(signs):
        chain, prev = [], None
        for i, s in enumerate(signs):
            r = (ru[i] if s > 0 else -rd[i])
            cl = math.cos(lats[i])
            dE = r * pes[i] / (111.32 * cl) if abs(cl) > 1e-6 else 0.0
            dN = r * pns[i] / 111.32
            lon, lat = cent[i][0] + dE, cent[i][1] + dN
            if lat > 90.0:                    # 跨极
                lon += 180.0; lat = 180.0 - lat
            elif lat < -90.0:
                lon += 180.0; lat = -180.0 - lat
            if prev is not None:              # 经度连续化展开
                while lon - prev > 180: lon -= 360.0
                while lon - prev < -180: lon += 360.0
            chain.append((lon, lat)); prev = lon
        return chain

    up = build([1] * len(cent))
    dn = build([-1] * len(cent))
    ring = up + list(reversed(dn))
    ring = _resolve_selfint(ring)
    flat = []
    for lon, lat in ring:
        flat.extend([round(lon, 3), round(lat, 3)])
    return flat


def _resolve_selfint(ring):
    """自交清污：buffer(0) 拆解蝴蝶结，取面积最大的主体环。
    无 shapely 或本已简单时原样返回。"""
    try:
        from shapely.geometry import Polygon as _Poly
    except ImportError:
        return ring
    try:
        poly = _Poly(ring)
        if poly.is_valid:
            return ring
        fixed = poly.buffer(0)
        geoms = getattr(fixed, 'geoms', [fixed])
        best = max(geoms, key=lambda g: g.area)
        out = list(best.exterior.coords)[:-1]
        return [(float(a), float(b)) for a, b in out]
    except Exception:
        return ring


def buffer_band(track):
    """中心线加宽成带：track = [(lon, lat, r_km)]，沿轨迹垂向双向偏移本影半径。
    返回扁平 [lon,lat,...]。端点 r→0 自然收敛成尖（擦边形态）。"""
    left, right = [], []
    n = len(track)
    for i, (lon, lat, r) in enumerate(track):
        j0 = max(0, i - 1); j1 = min(n - 1, i + 1)
        dlon = track[j1][0] - track[j0][0]
        dlat = track[j1][1] - track[j0][1]
        latm = math.radians((track[j0][1] + track[j1][1]) / 2)
        e = dlon * math.cos(latm); nn = dlat
        L = math.hypot(e, nn)
        if L < 1e-12:
            e, nn = 1.0, 0.0
        else:
            e /= L; nn /= L
        # 垂向单位（km 空间）：(nn, -e) 与反向
        dN = r * nn / 111.32
        dE = r * (-e) / (111.32 * math.cos(latm))
        left.append((lon + dE, lat + dN))
        right.append((lon - dE, lat - dN))
    poly = left + list(reversed(right))
    flat = []
    for p in poly:
        flat.extend([round(p[0], 3), round(p[1], 3)])
    return flat


def perp_radius(Ps, c_lat, c_lon, pe, pn):
    """轮廓点相对影心在轨迹垂向上的最大偏移（km）。"""
    if not len(Ps):
        return 0.0
    lats = np.degrees(np.arctan2(Ps[:, 2], np.hypot(Ps[:, 0], Ps[:, 1])))
    # 简化：直接用经纬度差（小尺度）
    xs = np.array([ecef_to_latlon(p)[1] for p in Ps])
    ys = np.array([ecef_to_latlon(p)[0] for p in Ps])
    dE = (xs - c_lon) * 111.32 * math.cos(math.radians(c_lat))
    dN = (ys - c_lat) * 111.32
    proj = dE * pe + dN * pn
    return float(np.max(np.abs(proj))) if len(proj) else 0.0


# ---------------------------------------------------------------- 朔匹配

def find_new_moons(jd_center, span_days=45):
    d = ephem.next_new_moon(eph_date(jd_center - span_days))
    out = []
    for _ in range(6):
        jd = float(d) + JD_OFFSET
        if jd > jd_center + span_days:
            break
        out.append(jd)
        d = ephem.next_new_moon(d)
    return out


def match_conjunction(jd_hint, ganzhi_expect):
    """±45 天内找 civil 日（长安 LMT）干支 == 期望的朔。
    返回 (jd_tt, 朔日 civil jdn, matched, 实测干支)。civil 日先后按午夜/23 时边界试。"""
    best = None
    for jd_tt in find_new_moons(jd_hint):
        dt_s = dt_for_jd(jd_tt - 0.5)
        jd_ut = jd_tt - dt_s / 86400.0
        lmt = jd_ut + LMT_H / 24.0
        for shift in (0.0, 1.0 / 24.0):          # 午夜边界；23 时起始日界
            jdn = int(math.floor(lmt + shift + 0.5))
            gz = ganzhi(jdn)
            if gz == ganzhi_expect:
                return jd_tt, jdn, True, gz
            cand = (abs(jd_tt - jd_hint), jd_tt, jdn, gz)
            if best is None or cand[0] < best[0]:
                best = cand
    _, jd_tt, jdn, gz = best
    return jd_tt, jdn, False, gz


# ---------------------------------------------------------------- 单场全流程

def compute_eclipse(jd_tt_nm, want_polygons=True, window_min=270, dt_s=None):
    """给定锚点时刻(TT)，复算几何。返回 dict；无食返回 None。
    window_min：以锚点为原点的扫描半窗（分钟）。默认 ±270 适配「朔时刻」锚点；
    锚点本身带误差时调大，窗口内 argmax 自动重找食甚，返回 peakOffsetMin 供校验。
    dt_s：外部指定 ΔT（秒）。汉构建传官方目录逐条 ΔT；缺省用 Espenak & Meeus 多项式。"""
    dt_s = dt_s if dt_s is not None else dt_for_jd(jd_tt_nm - 0.5)
    minutes = np.arange(-window_min, window_min + 1, 1.0)
    n = len(minutes)
    mp_best = np.full(n, -1.0)
    mc_fp = np.zeros(n)
    foot_ok = np.zeros(n, bool)
    pt_store = [None] * n
    for i, m in enumerate(minutes):
        jd_tt = jd_tt_nm + m / 1440.0
        S, M = sun_moon_ecef(jd_tt, jd_tt - dt_s / 86400.0)
        fp = axis_footprint(S, M)
        if fp is not None:
            mp, mc, _, _, _ = mags(fp[None, :], S, M)
            mp_best[i] = mp[0]; mc_fp[i] = mc[0]; foot_ok[i] = True
            pt_store[i] = fp
        else:
            P = closest_surface_point(S, M)
            mp, _, _, _, _ = mags(P[None, :], S, M)
            mp_best[i] = mp[0]
            pt_store[i] = P
    if mp_best.max() <= 0:
        return None

    i_ge = int(np.argmax(mp_best))
    lo = max(0, i_ge - 4); hi = min(n - 1, i_ge + 4)
    for i in range(lo, hi + 1):                      # 1 分钟内取峰
        if mp_best[i] > mp_best[i_ge]:
            i_ge = i
    m_ge = float(minutes[i_ge])
    jd_ge_tt = jd_tt_nm + m_ge / 1440.0
    S_ge, M_ge = sun_moon_ecef(jd_ge_tt, jd_ge_tt - dt_s / 86400.0)
    P_ge = pt_store[i_ge]
    mp_ge, mc_ge, rs_ge, rm_ge, sep_ge = mag_at(P_ge, S_ge, M_ge)

    central = bool((foot_ok & (mc_fp >= 1.0)).any())
    c_idx = [i for i in range(n) if foot_ok[i] and mc_fp[i] >= 1.0]
    p_idx = [i for i in range(n) if mp_best[i] > 0]
    t0_p, t1_p = float(minutes[min(p_idx)]), float(minutes[max(p_idx)])
    if central:
        t0_u, t1_u = float(minutes[min(c_idx)]), float(minutes[max(c_idx)])
        etype = 'total' if rm_ge >= rs_ge else 'annular'
    else:
        t0_u = t1_u = None
        etype = 'partial'

    # 中心线：食甚 ±2.5h 内每 2 分钟（与宋口径一致）；同时逐点求本影垂向半宽
    central_line = []
    track3 = []          # (lon, lat, r_perp_km, lon_contour_ecef)
    if central:
        raw = []
        for m in np.arange(max(m_ge - 150, t0_u), min(m_ge + 150, t1_u) + 1e-9, 2.0):
            jd_tt = jd_tt_nm + m / 1440.0
            S, M = sun_moon_ecef(jd_tt, jd_tt - dt_s / 86400.0)
            fp = axis_footprint(S, M)
            if fp is None:
                continue
            lat, lon = ecef_to_latlon(fp)
            Pu = trace_contour(S, M, fp, True, nrays=48)
            raw.append((float(m), lon, lat, fp, Pu))
        for i, (m, lon, lat, fp, Pu) in enumerate(raw):
            j0 = max(0, i - 1); j1 = min(len(raw) - 1, i + 1)
            dlon = raw[j1][1] - raw[j0][1]
            dlat = raw[j1][2] - raw[j0][2]
            latm = math.radians((raw[j0][2] + raw[j1][2]) / 2)
            e = dlon * math.cos(latm); nn = dlat
            L = math.hypot(e, nn)
            if L < 1e-12:
                e, nn = 1.0, 0.0
            else:
                e /= L; nn /= L
            r = perp_radius(Pu, lat, lon, nn, -e)
            r = min(r, 350.0)
            central_line.append([round(lon, 3), round(lat, 3)])
            track3.append((lon, lat, r))
    umbra_poly = band_edges_from_contours(raw) if central and len(track3) >= 3 else []

    # shadowFrames：中心相位内每 4 分钟（= 中心线隔点取；偏食无 frames，与宋同口径）
    frames = []
    if central:
        for idx in range(0, len(raw), 2):
            m, lon, lat, fp, Pu = raw[idx]
            jd_tt = jd_tt_nm + m / 1440.0
            frames.append({"t": iso_utc(jd_tt - dt_s / 86400.0),
                           "lon": round(lon, 3), "lat": round(lat, 3),
                           "r": round(track3[idx][2], 1),
                           "alt": round(sun_alt(fp, sun_moon_ecef(jd_tt, jd_tt - dt_s / 86400.0)[0]), 1)})

    # 多边形：半影区（接触相位 4 分钟档并集包络）；本影带已由中心线加宽生成
    penumbra_poly = []
    if want_polygons:
        tP = np.arange(t0_p, t1_p + 1e-9, 4.0)
        SS_p, MM_p = [], []
        for m in tP:
            jd_tt = jd_tt_nm + m / 1440.0
            S, M = sun_moon_ecef(jd_tt, jd_tt - dt_s / 86400.0)
            SS_p.append(S); MM_p.append(M)
        env = []
        p_track = []
        for k in range(len(tP)):
            S, M = SS_p[k], MM_p[k]
            C = axis_footprint(S, M)
            if C is None:
                C = closest_surface_point(S, M)
            P = trace_contour(S, M, C, False)
            if len(P):
                env.append((k, P))
            lat, lon = ecef_to_latlon(C)
            p_track.append((lon, lat))
        if len(env) >= 2:
            penumbra_poly = polygon_from_envelope(env, p_track, SS_p, MM_p, False)

    # 观测点实况（±4.5h 全程 1 分钟步）
    stations_out = []
    P_st = [surface_ecef(s["lat"], s["lon"]) for s in STATIONS]
    n_st = [surface_normal(P) for P in P_st]
    best_mag = [0.0] * len(STATIONS); best_i = [None] * len(STATIONS); best_alt = [-90.0] * len(STATIONS)
    for i, m in enumerate(minutes):
        if mp_best[i] <= 0:
            continue
        jd_tt = jd_tt_nm + m / 1440.0
        S, M = sun_moon_ecef(jd_tt, jd_tt - dt_s / 86400.0)
        for si, Ps in enumerate(P_st):
            mpv, _, _, _, _ = mags(Ps[None, :], S, M)
            if mpv[0] > best_mag[si]:
                best_mag[si] = float(mpv[0]); best_i[si] = i
                Su = S - Ps
                best_alt[si] = 90.0 - math.degrees(math.acos(np.clip(np.dot(Su, n_st[si]) / np.linalg.norm(Su), -1, 1)))
    for si, st in enumerate(STATIONS):
        if best_i[si] is not None and best_mag[si] > 0 and best_alt[si] > 0:
            jd_tt = jd_tt_nm + minutes[best_i[si]] / 1440.0
            S, M = sun_moon_ecef(jd_tt, jd_tt - dt_s / 86400.0)
            fp = axis_footprint(S, M)
            if fp is None:
                fp = pt_store[best_i[si]]
            stations_out.append({
                "name": st["name"], "lon": st["lon"], "lat": st["lat"],
                "visible": True, "obsc": round(best_mag[si], 3),
                "alt": round(best_alt[si], 1),
                "maxTime": iso_utc(jd_tt - dt_s / 86400.0),
                "distKm": round(float(np.linalg.norm(P_st[si] - fp)))
            })
        else:
            stations_out.append({
                "name": st["name"], "lon": st["lon"], "lat": st["lat"],
                "visible": False, "obsc": 0.0,
                # 食甚时刻太阳实况高度：区分「半影未及（白天）」与「地平线下」
                "alt": round(sun_alt(P_st[si], S_ge), 1)
            })

    # 本影半径 / 带宽 / 中心持续（半径取食甚处轨迹垂向半宽）
    urad = width = dur = 0.0
    if central and track3:
        i_nearest = min(range(len(raw)), key=lambda i: abs(raw[i][0] - m_ge))
        urad = track3[i_nearest][2]
        width = 2 * urad
        inside = 0
        for s in range(-900, 901):
            jd_tt = jd_ge_tt + s / 86400.0
            S, M = sun_moon_ecef(jd_tt, jd_tt - dt_s / 86400.0)
            _, mcv, _, _, _ = mag_at(P_ge, S, M)
            if mcv >= 1.0:
                inside += 1
        dur = float(inside)

    lat_c, lon_c = ecef_to_latlon(P_ge)
    return {
        "type": etype, "central": central,
        "peakOffsetMin": round(m_ge, 1),
        "center": {"lon": round(lon_c, 3), "lat": round(lat_c, 3), "alt": round(sun_alt(P_ge, S_ge), 1)},
        "maxMagnitude": round(mp_ge, 2),
        "pathWidthKm": round(width, 1), "umbraRadiusKm": round(urad, 1),
        "penumbraRadiusDeg": round(math.degrees(rs_ge + rm_ge - sep_ge), 2),
        "durationSec": round(dur),
        "timeRange": {
            "start": iso_utc(jd_tt_nm + (m_ge - 150) / 1440.0 - dt_s / 86400.0),
            "maxEclipse": iso_utc(jd_tt_nm + m_ge / 1440.0 - dt_s / 86400.0),
            "end": iso_utc(jd_tt_nm + (m_ge + 150) / 1440.0 - dt_s / 86400.0),
        },
        "centralLine": central_line,
        "umbraPolygon": umbra_poly,
        "penumbraPolygon": penumbra_poly,
        "shadowFrames": frames,
        "stations": stations_out,
        "utLocalDay": int(math.floor(jd_tt_nm - dt_s / 86400.0 + LMT_H / 24.0 + 0.5)),
    }


# ---------------------------------------------------------------- 验证

def next_nm_after(datestr):
    d = ephem.next_new_moon(eph_date(_jd_from_iso_greg(datestr)))
    return float(d) + JD_OFFSET


def _jd_from_iso_greg(s):
    y, m, d = [int(x) for x in s.split('-')]
    # 格里历 JDN
    a = (14 - m) // 12; yy = y + 4800 - a; mm = m + 12 * a - 3
    return (d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045) - 0.5


def validate():
    print("=== 验证 1：2024-04-08 现代日食（NASA：食带 墨西哥→美国→加拿大） ===")
    jd_nm = next_nm_after('2024-04-07')
    print("  ephem 朔时刻(UT 口径检查):", iso_utc(jd_nm), "（实际新月 ≈ 18:21 UTC）")
    r = compute_eclipse(jd_nm)
    print("  类型:", r['type'], "| maxMag:", r['maxMagnitude'], "| 中心:", r['center'],
          "| 带宽:", r['pathWidthKm'], "km | 全食:", r['durationSec'], "s")
    print("  中心线首2:", r['centralLine'][:2], " 末2:", r['centralLine'][-2:])
    print("  timeRange:", r['timeRange'], "| 帧数:", len(r['shadowFrames']))
    for st in r['stations']:
        print("  观测点:", st)

    print("\n=== 验证 2：960-05-28 对照宋存量几何（song.js 0001 环食） ===")
    jd_nm2 = next_nm_after('960-05-25') if False else _jd_nm_960()
    r2 = compute_eclipse(jd_nm2)
    src = open(os.path.join(ROOT, 'data/song.js'), encoding='utf-8').read()
    j = src.index('=', src.index('.song'))
    ref = next(x for x in json.loads(src[j + 1:].strip().rstrip(';'))['records'] if x['id'] == '0001')
    print("  宋存  center", ref['center'], "| maxMag", ref['maxMagnitude'], "| width", ref['pathWidthKm'],
          "| umbraR", ref['umbraRadiusKm'], "| dur", ref['durationSec'])
    print("  复算  center", r2['center'], "| maxMag", r2['maxMagnitude'], "| width", r2['pathWidthKm'],
          "| umbraR", r2['umbraRadiusKm'], "| dur", r2['durationSec'])
    print("  宋存  centralLine 首2:", ref['centralLine'][:2], "末2:", ref['centralLine'][-2:])
    print("  复算  centralLine 首2:", r2['centralLine'][:2], "末2:", r2['centralLine'][-2:])
    print("  宋存  frames[0]:", ref['shadowFrames'][0], "| 帧数", len(ref['shadowFrames']))
    print("  复算  frames[0]:", r2['shadowFrames'][0], "| 帧数", len(r2['shadowFrames']))
    for st in r2['stations']:
        print("  观测点:", st)


def _jd_nm_960():
    # 960-05-28 是 Julian 历标签；格里历同日 = 960-06-01 前后 → 直接在儒略历 JDN 附近搜朔
    jdn = jdn_julian(960, 5, 28)
    return float(ephem.next_new_moon(eph_date(jdn - 0.5 - 8))) + JD_OFFSET


# ---------------------------------------------------------------- 全量构建

def _jd_from_label(label):
    y, m, d = [int(x) for x in label.split('-')]
    return float(jdn_julian(y, m, d)) - 0.5


def wide_rematch(rec):
    """对主流程标记「该朔全球无食」的条目：±400 天内重找「civil 日干支吻合且有真实食」的朔。
    找到 → 用其几何与日期（纪月按原文保留，脚注标注重配）；找不到 → 保留降级。"""
    hint = _jd_from_label(rec['dateLabel'])
    gz = rec['extra']['ganzhi']
    d = ephem.next_new_moon(eph_date(hint - 400))
    best = None
    for _ in range(60):
        jd_tt = float(d) + JD_OFFSET
        if jd_tt > hint + 400:
            break
        dt_s = dt_for_jd(jd_tt - 0.5)
        jd_ut = jd_tt - dt_s / 86400.0
        lmt = jd_ut + LMT_H / 24.0
        for shift in (0.0, 1.0 / 24.0):
            jdn = int(math.floor(lmt + shift + 0.5))
            if ganzhi(jdn) == gz:
                r = compute_eclipse(jd_tt, want_polygons=True)
                if r is not None:
                    dist = abs(jd_tt - hint)
                    if best is None or dist < best[0]:
                        best = (dist, jd_tt, jdn, r)
                break
        d = ephem.next_new_moon(d)
    return best


def run_wide():
    src = open(os.path.join(ROOT, 'data/tang.js'), encoding='utf-8').read()
    j = src.index('=', src.index('.tang'))
    head = src[:j + 1]
    obj = json.loads(src[j + 1:].strip().rstrip(';'))
    n_rem = n_keep = 0
    for rec in obj['records']:
        if not str(rec['extra'].get('match', '')).startswith('该朔全球无食'):
            continue                      # 只处理主流程标记的无食条目
        best = wide_rematch(rec)
        if best is None:
            n_keep += 1
            e = rec['extra']
            e['match'] = '历朔重配未果：±400 天内无「干支吻合且有食」之朔，星历判该朔全球无食'
            e['dateMethod'] = '干支朔日反推（±1 日）；星历判无食，历日存疑'
            rec['type'] = 'none'
            rec['visibility'] = 'unseen'
            print(f"  {rec['id']} {rec['era']} {rec['extra']['ganzhi']}: 保留降级（星历判无食）")
            continue
        dist, jd_tt, jdn_nm, r = best
        rec['dateLabel'] = date_label_from_jdn(jdn_nm)
        rec['dateRaw'] = rec['dateLabel']
        rec['sortKey'] = int(rec['dateLabel'].replace('-', ''))
        rec['type'] = r['type']
        rec['visibility'] = 'visible' if any(s['visible'] for s in r['stations']) else 'unseen'
        for k in ('center', 'maxMagnitude', 'pathWidthKm', 'umbraRadiusKm',
                  'penumbraRadiusDeg', 'durationSec', 'timeRange', 'centralLine',
                  'umbraPolygon', 'penumbraPolygon', 'shadowFrames', 'stations'):
            rec[k] = r[k]
        e = rec['extra']
        e.pop('magIsDemo', None); e.pop('centerIsDemo', None)
        cap = next(s for s in r['stations'] if s['name'] == '长安')
        e['mag'] = cap['obsc']; e['alt'] = cap['alt']
        e['dateMethod'] = '远窗历朔重配（原纪月与星历不符，按干支+食限定日）'
        e['match'] = '远窗干支吻合（原纪月存疑）'
        n_rem += 1
        cap = next(s for s in r['stations'] if s['name'] == '长安')
        print(f"  {rec['id']} {rec['era']} {rec['extra']['ganzhi']}: 重配 → {rec['dateLabel']} "
              f"{r['type']} maxMag={r['maxMagnitude']:.2f} 长安{cap['obsc']:.2f}/{cap['alt']:.1f}°")
        sys.stdout.flush()
    obj['records'] = [x for x in obj['records']]
    with open(os.path.join(ROOT, 'data/tang.js'), 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print(f"远窗重配 {n_rem} 条，保留降级 {n_keep} 条，已写回 data/tang.js")


def run_tang():
    src = open(os.path.join(ROOT, 'data/tang.js'), encoding='utf-8').read()
    j = src.index('=', src.index('.tang'))
    head = src[:j + 1]
    obj = json.loads(src[j + 1:].strip().rstrip(';'))
    out = []
    for rec in obj['records']:
        era, gz = rec['era'], rec['extra']['ganzhi']
        jd_hint = _jd_from_label(rec['dateLabel'])
        jd_tt, jdn_nm, matched, gz_found = match_conjunction(jd_hint, gz)
        r = compute_eclipse(jd_tt)
        if r is None:
            e = rec['extra']
            e['match'] = '该朔全球无食（±45 日内干支吻合之朔未见食，或干支无吻合之朔）'
            print(f"  {rec['id']} {era} {gz}: 星历判无食，标记待远窗重配")
            out.append(rec); continue
        # dateLabel = 食甚所在 civil 日（= 朔/晦日，干支匹配所得）
        rec['dateLabel'] = date_label_from_jdn(jdn_nm)
        rec['dateRaw'] = rec['dateLabel']
        rec['sortKey'] = int(rec['dateLabel'].replace('-', ''))
        rec['type'] = r['type']
        rec['visibility'] = 'visible' if any(s['visible'] for s in r['stations']) else 'unseen'
        for k in ('center', 'maxMagnitude', 'pathWidthKm', 'umbraRadiusKm',
                  'penumbraRadiusDeg', 'durationSec', 'timeRange', 'centralLine',
                  'umbraPolygon', 'penumbraPolygon', 'shadowFrames', 'stations'):
            rec[k] = r[k]
        e = rec['extra']
        e.pop('magIsDemo', None); e.pop('centerIsDemo', None)
        cap = next(s for s in r['stations'] if s['name'] == '长安')
        e['mag'] = cap['obsc']; e['alt'] = cap['alt']
        e['dateMethod'] = '历朔干支星历匹配（精确朔日）'
        e['match'] = '干支吻合' if matched else '干支不符（星历朔日干支 ' + gz_found + '）'
        out.append(rec)
        ly = next(s for s in r['stations'] if s['name'] == '洛阳')
        print(f"  {rec['id']} {era} {gz} → {rec['dateLabel']} {r['type']:7s} "
              f"{'中心' if r['central'] else '偏食':2s} maxMag={r['maxMagnitude']:.2f} "
              f"带={r['pathWidthKm']:6.1f}km 长安{cap['obsc']:.2f}/{cap['alt']:5.1f}° "
              f"洛阳{ly['obsc']:.2f}/{ly['alt']:5.1f}° 帧{len(r['shadowFrames']):3d} "
              f"{'✓' if matched else '✗干支→' + gz_found}")
        sys.stdout.flush()
    obj['records'] = out
    meta = dict(obj.get('_meta', {}))
    meta['note'] = ('《新唐书·天文志二》93 条；原文照录；几何由 PyEphem + 矢量影锥复算'
                    '（WGS84 椭球，ΔT: Espenak & Meeus 2006）；历朔干支星历匹配定日。')
    obj['_meta'] = meta
    with open(os.path.join(ROOT, 'data/tang.js'), 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print("已写回 data/tang.js")


if __name__ == '__main__':
    if '--validate' in sys.argv:
        validate()
    elif '--wide' in sys.argv:
        run_wide()
    else:
        run_tang()

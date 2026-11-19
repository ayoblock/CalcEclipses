#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汉代日食星历复算（tools/build_han_geom.py）—— 官方目录锚定版

数据来源与根因说明：
  · 原表（tmp/han 三国时代旧管线）的星历字段（jd/instant/slat/slon）经与 NASA
    五千年目录官方 ASCII（tmp/5MKSEcatalog.txt，Espenak & Meeus NASA/TP-2008-214170）
    逐条比对，证实有系统性错误（-204-12-20：原表 TD 03:42 / mag 0.58 / 中心 -23.7,124.9
    vs 官方 TD 07:18:35 / mag 0.8464 / 中心 66.0N,114.4E）。原表的「中心」实为月球下点，
    时刻为缺陷管线给出的错误朔时刻。原表的「长安本地值」（mag 0.58 / alt 28）与官方
    复算吻合，予以保留。
  · 引擎星历层已由 pyephem 换为 pymeeus（ELP-2000/82 全项 + VSOP87，与 NASA 同理论族）；
    pyephem 古代月球黄经系统性偏差（BC ≈1.8°≈3.5h）是上述错误的根源之一。

本脚本流程：
  1. 解析官方目录，按儒略历日期逐条匹配《汉书》54 条记录；
  2. 以官方 TD of greatest eclipse 为 TT 锚、官方 ΔT 建地球自转角，窗口内重扫食甚；
  3. compute_eclipse 全流程：中心线 / 本影带 / 半影包络 / 逐帧影心 / 长安实况；
  4. 每条打印与官方值的交叉校验（食分、中心距离、时刻偏移、长安实况 vs 原表）；
  5. 合并回 data/han.js（原表值全保留于 extra；官方值入 extra.cat）。
  noecl 条目：官方目录 ±3 日内如有日食，仅记录近邻参考（供「历日存疑」呈现），
  不生成几何，保留降级。
"""
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tang_geom as tg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, 'tmp', '5MKSEcatalog.txt')

# 汉：只有长安一个观测地（与原表口径一致 108.9/34.3）
tg.STATIONS = [{"name": "长安", "lon": 108.9, "lat": 34.3}]

MONTHS = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6,
              Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)

CAT_RE = re.compile(
    r'^\s*(\d+)\s+(\d+)\s+(-?\d{1,4})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+'
    r'(\d{1,2}):(\d{2}):(\d{2})\s+(\d+)\s+(-?\d+)\s+(-?\d+)\s+([TAHP][+\w]?)\s+'
    r'([ntp-]{2})\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+([\d.]+[NS])\s+([\d.]+[EW])\s+(-?\d+)\s+(\d+)')


def parse_catalog():
    out = {}
    with open(CATALOG, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = CAT_RE.match(line)
            if not m:
                continue
            (num, plate, y, mon, d, hh, mm, ss, dt, luna, saros,
             typ, qle, gamma, mag, lat, lon, salt, sazm) = m.groups()
            y = int(y)
            mon = MONTHS[mon]
            lat = float(lat[:-1]) * (1 if lat[-1] == 'N' else -1)
            lon = float(lon[:-1]) * (1 if lon[-1] == 'E' else -1)
            td_h = int(hh) + int(mm) / 60 + int(ss) / 3600
            typ = typ.rstrip('+')          # 目录有 A+/P* 等变体
            out[(y, mon, int(d))] = {
                'catNum': int(num), 'typeLetter': typ, 'tdH': td_h,
                'tdText': f'{int(hh):02d}:{mm}:{ss}', 'dt': int(dt),
                'gamma': float(gamma), 'mag': float(mag),
                'lat': lat, 'lon': lon, 'sunAlt': int(salt),
            }
    return out


def label_to_ymd(label):
    m = re.match(r'^(前|公元)?(\d{1,4})年(\d{1,2})月(\d{1,2})日$', label)
    if not m:
        return None
    y = int(m.group(2))
    if m.group(1) == '前':
        y = 1 - y                       # 前205年 → 天文年 -204
    return (y, int(m.group(3)), int(m.group(4)))


def hav_km(lat1, lon1, lat2, lon2):
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dla = la2 - la1; dlo = math.radians(lon2 - lon1)
    a = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def iso6(s):
    """BC 年份统一为 6 位扩展 ISO（-204-… → -00204-…）；AD 年份保持 4 位。"""
    m = re.match(r'^(-?\d{1,4})-(\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$', s)
    if not m:
        return s
    y = int(m.group(1))
    if y >= 0:
        return s
    return '-%06d-%s' % (-y, m.group(2))


def fix_iso_deep(rec):
    tr = rec.get('timeRange') or {}
    for k in ('start', 'maxEclipse', 'end'):
        if tr.get(k):
            tr[k] = iso6(tr[k])
    for f in rec.get('shadowFrames', []):
        f['t'] = iso6(f['t'])
    for st in rec.get('stations', []):
        if st.get('maxTime'):
            st['maxTime'] = iso6(st['maxTime'])


def run():
    cat = parse_catalog()
    print(f'官方目录解析：{len(cat)} 条（-1999..+3000）')

    src = open(os.path.join(ROOT, 'data/han.js'), encoding='utf-8').read()
    j = src.index('=', src.index('.han'))
    head = src[:j + 1]
    obj = json.loads(src[j + 1:].strip().rstrip(';'))
    recs = obj['records']

    n_geom = n_keep = 0
    v_mag, v_km, v_td = [], [], []
    for rec in recs:
        e = rec['extra']
        rid = rec['id']
        ymd = label_to_ymd(rec['dateLabel'])
        vis = rec.get('visibility')

        # 旗标（左栏 chips 计数真实化；visibility 语义保留原表口径）
        rec['flags'] = {'noecl': ['noEclipse'], 'nolat': ['notAtStation'],
                        'below': ['belowHorizon']}.get(vis, [])

        if ymd is None or vis == 'noecl' or ymd not in cat:
            n_keep += 1
            if ymd in cat:
                pass
            elif vis == 'noecl':
                # 官方目录 ±3 日近邻参考
                near = []
                jdn0 = tg.jdn_julian(*ymd) if ymd else None
                if jdn0:
                    for (cy, cm, cd), c in cat.items():
                        dd = abs(tg.jdn_julian(cy, cm, cd) - jdn0)
                        if dd <= 3:
                            near.append({'date': f'{cy}-{cm:02d}-{cd:02d}',
                                         'type': c['typeLetter'], 'mag': c['mag'], 'off': dd})
                near.sort(key=lambda x: x['off'])
                e['catNear'] = near[:3]
                print(f"  #{rid} {rec['era']}: 全球无食（noecl），官方目录±3日近邻 {len(near)} 条")
            elif ymd:
                print(f"  #{rid} {rec['era']} {rec['dateLabel']}: ⚠ 官方目录无该日条目！保留降级")
            continue

        c = cat[ymd]
        jd_tt = tg.jdn_julian(*ymd) - 0.5 + c['tdH'] / 24.0
        r = tg.compute_eclipse(jd_tt, window_min=180, dt_s=c['dt'])
        if r is None:
            n_keep += 1
            e['recheck'] = '官方目录有食但引擎复算未见（需人工核查）'
            print(f"  #{rid} {rec['era']}: ⚠ 引擎复算无食！")
            continue

        # ---- 与官方目录交叉校验 ----
        d_km = hav_km(r['center']['lat'], r['center']['lon'], c['lat'], c['lon'])
        v_mag.append(abs(r['maxMagnitude'] - c['mag']))
        v_km.append(d_km)
        v_td.append(abs(r['peakOffsetMin']))
        cap = next((s for s in r['stations'] if s['name'] == '长安'), None)
        warn = ''
        if d_km > 150: warn += ' ⚠中心偏差'
        if abs(r['maxMagnitude'] - c['mag']) > 0.02: warn += ' ⚠食分偏差'
        if abs(r['peakOffsetMin']) > 5: warn += ' ⚠时刻偏差'
        # 与原表长安实况比对（原表本地值可信）
        dmag = abs(cap['obsc'] - e['mag']) if (cap and cap.get('obsc') is not None and e.get('mag')) else None
        if dmag is not None and dmag > 0.08: warn += f' ⚠长安食分vs原表({e["mag"]})'
        print(f"  #{rid} {rec['era']:8s} {rec['dateLabel']:14s} {r['type']:7s} "
              f"mag {r['maxMagnitude']:.2f}/{c['mag']:.2f} 中心Δ{d_km:5.0f}km "
              f"TDΔ{r['peakOffsetMin']:+.0f}min 长安算{cap['obsc']:.2f}/{cap['alt']:5.1f}°"
              f" 表{e.get('mag')}/{e.get('alt')}{warn}")
        sys.stdout.flush()

        # ---- 合并 ----
        rec['type'] = r['type']
        e['cat'] = {'td': c['tdText'], 'dt': c['dt'], 'gamma': c['gamma'],
                    'mag': c['mag'], 'lat': c['lat'], 'lon': c['lon'],
                    'type': c['typeLetter'], 'catNum': c['catNum']}
        for k in ('center', 'maxMagnitude', 'pathWidthKm', 'umbraRadiusKm',
                  'penumbraRadiusDeg', 'durationSec', 'timeRange', 'centralLine',
                  'umbraPolygon', 'penumbraPolygon', 'shadowFrames', 'stations'):
            rec[k] = r[k]
        fix_iso_deep(rec)
        n_geom += 1

    print(f"\n几何复算 {n_geom} 条，降级/无锚 {n_keep} 条")
    if v_mag:
        print(f"食分 vs 官方：最大偏差 {max(v_mag):.3f}")
        print(f"中心 vs 官方：最大 {max(v_km):.0f} km，中位 {sorted(v_km)[len(v_km)//2]:.0f} km")
        print(f"食甚时刻 vs 官方 TD：最大偏移 {max(v_td):.1f} min")
    obj['_meta'] = dict(obj.get('_meta', {}), note=(
        '《汉书·五行志》54 条；原文照录；几何由 pymeeus（ELP-2000/82 + VSOP87）+ 矢量影锥复算'
        '（WGS84 椭球），逐条以 NASA 五千年目录官方值（TD/ΔT/γ/mag/中心坐标）锚定并交叉校验；'
        '原表旧星历字段证实有系统误差，仅长安本地实况值可信，均保留于 extra。'))
    with open(os.path.join(ROOT, 'data/han.js'), 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print("已写回 data/han.js")


if __name__ == '__main__':
    run()

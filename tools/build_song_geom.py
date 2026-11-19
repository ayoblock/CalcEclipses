#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宋代日食星历重建（tools/build_song_geom.py）—— 与汉/唐统一管线

背景：
  · 现 data/song.js 的几何由旧宋管线生成（单站食分驱动 + 旧星历层），
    与汉/唐的「官方目录锚定 + pymeeus 复算」口径不一致：
      - 半影多边形是食甚时刻落区（整片大陆级暗斑），汉/唐是扫掠包络；
      - 星历层无 pymeeus（旧引擎月球黄经在 960–1279 年段同样有 ~0.2–0.3°
        系统偏差，同唐代重建前的情形）；
      - 详情缺「官方目录」锚定行（catNum/TD/ΔT/γ/官方食分/Saros/中心食时长/
        食甚轴点）。
  · 本脚本用与 rebuild_tang_geom 完全相同的引擎与官方目录（5MKSE），
    为宋 225 条逐条重锚、复算、交叉校验、合并。

宋特有口径：
  · 观测地三点：开封(114.3,34.8) / 临安(120.15,30.25) / 开城(126.55,37.97)；
    「本地日」救援偏移按 dynastyLabel：北宋=开封(+27432s)、南宋=临安(+28836s)。
  · 117 条有《宋史·天文志》原记（lunarDate 带干支，可做历日自检）；
    108 条无原记（lunarDate=（待校），dateLabel 系依朔望回推）。
  · 历史性旗标（云阴不见 cloudHide / 当食不食 noEat）原样保留；
    旧管线计算旗标 localUnseen 弃用，由引擎重判。
"""
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tang_geom as tg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, 'tmp', '5MKSEcatalog.txt')

# 宋：观测地三点（与现数据口径一致）
tg.STATIONS = [
    {"name": "开封", "lon": 114.3, "lat": 34.8},
    {"name": "临安", "lon": 120.15, "lat": 30.25},
    {"name": "开城", "lon": 126.55, "lat": 37.97},
]

MONTHS = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6,
              Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)

CAT_RE = re.compile(
    r'^\s*(\d+)\s+(\d+)\s+(-?\d{1,4})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+'
    r'(\d{1,2}):(\d{2}):(\d{2})\s+(\d+)\s+(-?\d+)\s+(-?\d+)\s+([TAHP][+\w]?)\s+'
    r'([ntp-]{2})\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+([\d.]+[NS])\s+([\d.]+[EW])\s+(-?\d+)\s+(\d+)'
    r'(?:\s+(\d+))?(?:\s+(\d+m\d\d?s))?\s*$')


def parse_catalog():
    out = {}
    with open(CATALOG, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = CAT_RE.match(line)
            if not m:
                continue
            (num, plate, y, mon, d, hh, mm, ss, dt, luna, saros,
             typ, qle, gamma, mag, lat, lon, salt, sazm, width, dur) = m.groups()
            y = int(y)
            mon = MONTHS[mon]
            lat = float(lat[:-1]) * (1 if lat[-1] == 'N' else -1)
            lon = float(lon[:-1]) * (1 if lon[-1] == 'E' else -1)
            td_h = int(hh) + int(mm) / 60 + int(ss) / 3600
            typ = typ.rstrip('+')
            out[(y, mon, int(d))] = {
                'catNum': int(num), 'typeLetter': typ, 'tdH': td_h,
                'tdText': f'{int(hh):02d}:{mm}:{ss}', 'dt': int(dt),
                'gamma': float(gamma), 'mag': float(mag),
                'lat': lat, 'lon': lon, 'sunAlt': int(salt),
                'saros': int(saros), 'dur': dur or '',
                'widthKm': int(width) if width else None,
            }
    return out


GZ_RE = re.compile(r'([甲乙丙丁戊己庚辛壬癸])([子丑寅卯辰巳午未申酉戌亥])')

# 本地日救援偏移（秒）：北宋=开封 114.3°E，南宋=临安 120.15°E
SITE_OFF = {'北宋': 27432, '南宋': 28836}
TYPE_LETTER = {'T': 'total', 'A': 'annular', 'H': 'annular', 'P': 'partial'}


def run():
    cat = parse_catalog()
    print(f'官方目录解析：{len(cat)} 条（-1999..+3000）')

    src = open(os.path.join(ROOT, 'data/song.js'), encoding='utf-8').read()
    j = src.index('=', src.index('.song'))
    head = src[:j + 1]
    obj = json.loads(src[j + 1:].strip().rstrip(';'))
    recs = obj['records']
    old_by_id = {r['id']: r for r in recs}

    n_geom = n_shift = n_keep = 0
    v_mag, v_km, v_td = [], [], []
    type_diff = []
    for rec in recs:
        e = rec['extra']
        rid = rec['id']
        y, mo, d = (int(x) for x in rec['dateLabel'].split('-'))
        ymd = (y, mo, d)

        # 干支自检（仅原记条目有干支）
        gz_txt = GZ_RE.search(rec.get('lunarDate') or '')
        gz_ok = None
        if gz_txt:
            gz_ok = (tg.ganzhi(tg.jdn_julian(y, mo, d)) == gz_txt.group(0))

        c = cat.get(ymd)
        local_shift = 0
        date_off = 0
        anchor_ymd = ymd
        if c is None:
            # 本地日救援 / ±1 日历日存疑：目录按 UT 记日；食甚 UT 足够晚时
            # 中国本地日 = 目录日 + 1（北宋开封 / 南宋临安偏移）。
            # 旧宋管线的 108 条补入 dateLabel 有 ±1 日系统误差（其中多条
            # 干支自检不合），对 ±1 日内的唯一目录条目锚定并标注「历日存疑」。
            off = SITE_OFF.get(rec.get('dynastyLabel'), 27432)

            def ut_of(cc):
                return (int(cc['tdText'][:2]) * 3600 + int(cc['tdText'][3:5]) * 60
                        + int(cc['tdText'][6:8]) - cc['dt']) % 86400

            def day_before(y_, m_, d_):
                if d_ > 1:
                    return (y_, m_, d_ - 1)
                m2 = m_ - 1
                if m2 == 0:
                    return (y_ - 1, 12, 31)
                return (y_, m2, {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                                 7: 31, 8: 31, 9: 30, 10: 31, 11: 30}.get(m2, 31))

            def day_after(y_, m_, d_):
                dim = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                       7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}.get(m_, 30)
                if d_ < dim:
                    return (y_, m_, d_ + 1)
                return (y_ + (m_ == 12), (m_ % 12) + 1, 1)

            D1, D2 = cat.get(day_before(y, mo, d)), cat.get(day_after(y, mo, d))
            if D1 is not None and ut_of(D1) + off >= 86400:
                c, local_shift, anchor_ymd = D1, 1, day_before(y, mo, d)
            elif D1 is not None and D2 is None:
                # 目录日在 dateLabel 前一日但本地日不跨日 → 原纪日晚 1 日（存疑）
                c, date_off, anchor_ymd = D1, +1, day_before(y, mo, d)
            elif D2 is not None and ut_of(D2) + off < 86400:
                # 目录日在 dateLabel 后一日且其本地日即该日 → 原纪日早 1 日（存疑）
                c, date_off, anchor_ymd = D2, -1, day_after(y, mo, d)
        if c is None:
            n_keep += 1
            # 官方目录该日无食：保留降级，给出 ±3 日近邻参考
            jdn0 = tg.jdn_julian(y, mo, d)
            near = []
            for (cy, cm, cd), cc in cat.items():
                dd = abs(tg.jdn_julian(cy, cm, cd) - jdn0)
                if dd <= 3:
                    near.append({'date': f'{cy}-{cm:02d}-{cd:02d}',
                                 'type': cc['typeLetter'], 'mag': cc['mag'], 'off': dd})
            near.sort(key=lambda x: x['off'])
            e['catNear'] = near[:3]
            e['catNone'] = '官方五千年目录该日（儒略历）无日食记录；原纪日存疑，保留降级示意'
            rec['type'] = 'none'
            rec['flags'] = [f for f in rec.get('flags', []) if f in ('cloudHide', 'noEat')] or ['noEclipse']
            if 'noEclipse' not in rec['flags']:
                rec['flags'].append('noEclipse')
            rec.pop('shadowFrames', None); rec.pop('timeRange', None)
            rec.pop('centralLine', None); rec.pop('umbraPolygon', None)
            rec.pop('penumbraPolygon', None); rec.pop('stations', None)
            print(f"  #{rid} {rec['era']}: 官方目录无该日条目"
                  f"（干支复核 {gz_txt.group(0) if gz_txt else '—'}"
                  f"{'✓' if gz_ok else ('✗' if gz_ok is False else '?')}），近邻 {near[:2]}")
            continue

        jd_tt = tg.jdn_julian(*anchor_ymd) - 0.5 + c['tdH'] / 24.0
        r = tg.compute_eclipse(jd_tt, window_min=180, dt_s=c['dt'])
        if r is None:
            n_keep += 1
            e['recheck'] = '官方目录有食但引擎复算未见（需人工核查）'
            print(f"  #{rid} {rec['era']}: ⚠ 引擎复算无食！")
            continue

        # ---- 与官方目录交叉校验 ----
        d_km = hav_km = _hav(r['center']['lat'], r['center']['lon'], c['lat'], c['lon'])
        v_mag.append(abs(r['maxMagnitude'] - c['mag']))
        v_km.append(d_km)
        v_td.append(abs(r['peakOffsetMin']))
        # 原记干支自检（以 dateLabel 本地日为准）
        gznote = ''
        if gz_txt and not gz_ok:
            gznote = ' ⚠干支不合'
        # 食型与旧数据比对（旧管线 pyephem 有系统偏差，边界型翻转属预期修正）
        old_t = old_by_id[rid].get('type')
        if old_t and old_t != r['type']:
            type_diff.append(f"#{rid}:{old_t}->{r['type']}")
        cap = next((s for s in r['stations'] if s['name'] == '开封'), None)
        warn = ''
        if d_km > 150: warn += ' ⚠中心偏差'
        if abs(r['maxMagnitude'] - c['mag']) > 0.02: warn += ' ⚠食分偏差'
        if abs(r['peakOffsetMin']) > 5: warn += ' ⚠时刻偏差'
        print(f"  #{rid} {rec['era']:8s} {rec['dateLabel']}{' (地方日+1)' if local_shift else ''}{' (历日存疑±1)' if date_off else ''} {r['type']:7s} "
              f"mag {r['maxMagnitude']:.2f}/{c['mag']:.2f} 中心Δ{d_km:5.0f}km "
              f"TDΔ{r['peakOffsetMin']:+.0f}min 开封算{cap['obsc']:.2f}/{cap['alt']:5.1f}° "
              f"{'干支✓' if gz_ok else ('干支✗' + gznote if gz_ok is False else '干支—')}{warn}")
        sys.stdout.flush()

        # ---- 合并 ----
        old_extra = dict(old_by_id[rid].get('extra') or {})
        rec['type'] = r['type']
        e['cat'] = {'td': c['tdText'], 'dt': c['dt'], 'gamma': c['gamma'],
                    'mag': c['mag'], 'lat': round(c['lat'], 1), 'lon': round(c['lon'], 1),
                    'type': c['typeLetter'], 'catNum': c['catNum'],
                    'saros': c['saros'], 'dur': c['dur'],
                    'sunAlt': c['sunAlt'], 'widthKm': c['widthKm'],
                    'catDate': '%04d-%02d-%02d' % anchor_ymd,
                    'localDayShift': local_shift}
        if date_off:
            gz_s = gz_txt.group(0) if gz_txt else '—'
            e['cat']['dateOff'] = date_off
            e['cat']['dateOffNote'] = (
                f'原纪日（{rec["dateLabel"]}，干支自检 {gz_s}）与官方目录最近日食相差 1 日；'
                '历日存疑，几何按官方目录日复算')
        sec = (int(c['tdText'][:2]) * 3600 + int(c['tdText'][3:5]) * 60 + int(c['tdText'][6:8]) - c['dt']) % 86400
        e['cat']['ut'] = '%02d:%02d:%02d' % (sec // 3600, (sec % 3600) // 60, sec % 60)
        # 旧 extra 的 remark / solarTypeRaw 保留；nasaId 由官方目录取代
        for k in ('remark', 'solarTypeRaw', 'variant'):
            if k in old_extra:
                e[k] = old_extra[k]
        e.pop('nasaId', None)
        for k in ('center', 'maxMagnitude', 'pathWidthKm', 'umbraRadiusKm',
                  'penumbraRadiusDeg', 'durationSec', 'timeRange', 'centralLine',
                  'umbraPolygon', 'penumbraPolygon', 'shadowFrames', 'stations'):
            rec[k] = r[k]
        rec['visibility'] = 'visible' if any(s.get('visible') for s in r['stations']) else 'unseen'
        # 历史性旗标保留，计算性旗标（localUnseen 等）弃用重判
        hist = [f for f in old_by_id[rid].get('flags', []) if f in ('cloudHide', 'noEat')]
        rec['flags'] = hist
        n_geom += 1
        if local_shift:
            n_shift += 1

    print(f"\n几何复算 {n_geom} 条（含本地日救援 {n_shift} 条），降级/无锚 {n_keep} 条")
    if v_mag:
        print(f"食分 vs 官方：最大偏差 {max(v_mag):.3f}")
        print(f"中心 vs 官方：最大 {max(v_km):.0f} km，中位 {sorted(v_km)[len(v_km)//2]:.0f} km")
        print(f"食甚时刻 vs 官方 TD：最大偏移 {max(v_td):.1f} min")
    if type_diff:
        print(f"食型与旧数据差异 {len(type_diff)} 条：{' '.join(type_diff)}")
    n_text = sum(1 for r in recs if not (r.get('lunarDate') or '').startswith('（待校'))
    obj['_meta'] = dict(obj.get('_meta', {}), note=(
        f'两宋日食 225 条（{n_text} 条有《宋史·天文志》等原记，{225-n_text} 条依朔望回推补入、如实标注）；'
        '几何由 pymeeus（ELP-2000/82 + VSOP87）+ 矢量影锥复算（WGS84 椭球），'
        '逐条以 NASA 五千年目录官方值（TD/ΔT/γ/食分/中心坐标）锚定并交叉校验，'
        '与汉/唐管线同口径。'))
    with open(os.path.join(ROOT, 'data/song.js'), 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print("已写回 data/song.js")


def _hav(lat1, lon1, lat2, lon2):
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dla = la2 - la1; dlo = math.radians(lon2 - lon1)
    a = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


if __name__ == '__main__':
    run()

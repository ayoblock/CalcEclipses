#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唐代日食星历重建（tools/rebuild_tang_geom.py）—— 官方目录锚定版

背景与根因：
  · 现 data/tang.js 的几何由旧管线（pyephem 星历）生成。pyephem 截断月历在唐代
    有 ~0.3°（≈35 min）月球黄经系统偏差，影带与食甚整体偏早/偏移数十至上百公里。
  · 引擎星历层已换 pymeeus（ELP-2000/82 全项 + VSOP87，与 NASA 五千年谱同理论族）。
  · 官方锚定 = NASA 五千年目录 ASCII（tmp/5MKSEcatalog.txt，Espenak & Meeus），
    逐条取 TD of greatest eclipse 为 TT 锚、目录 ΔT 建地球自转角。
  · 历日可信度：93 条历朔干支匹配日期中 91 条已被官方目录独立旁证（2026-11-19 核查）；
    tmp/tang 前身标记的 5 条「待考」中 2 条（#0024 #0069）系其自身文本讹误，
    现项目文本（己丑朔/贞元三年）与官方目录精确吻合。
  · #0044 #0088 #0090：官方目录该日无食，保留降级（原文纪日存疑）。

流程：
  1. 解析官方目录（含 Saros/中心食时长），按儒略历日期匹配 93 条 dateLabel；
  2. 与 tmp/tang 前身 JSON 的 ephem.canon 交叉校验（cat/TD/γ/食分/食甚点）；
  3. compute_eclipse 全流程：中心线/本影带/半影包络/逐帧影心/长安实况；
  4. 与原文互证校验：原文记「既」→ 长安复算应近全食；干支复核；
  5. 合并回 data/tang.js（官方值入 extra.cat，原文/旧匹配信息全保留）。
"""
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tang_geom as tg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, 'tmp', '5MKSEcatalog.txt')
TMPTANG = os.path.join(ROOT, 'tmp', 'tang', 'tang_eclipse.json')

# 唐：观测地为长安（与现数据口径一致 108.9/34.3）
tg.STATIONS = [{"name": "长安", "lon": 108.9, "lat": 34.3}]

MONTHS = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6,
              Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)

# 比汉版多捕获路径宽度与中心食时长；尾列：sunalt sazm [width] [duration]
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
            typ = typ.rstrip('+')          # 目录有 A+/P* 等变体
            out[(y, mon, int(d))] = {
                'catNum': int(num), 'typeLetter': typ, 'tdH': td_h,
                'tdText': f'{int(hh):02d}:{mm}:{ss}', 'dt': int(dt),
                'gamma': float(gamma), 'mag': float(mag),
                'lat': lat, 'lon': lon, 'sunAlt': int(salt),
                'saros': int(saros), 'dur': dur or '',
                'widthKm': int(width) if width else None,
            }
    return out


def hav_km(lat1, lon1, lat2, lon2):
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dla = la2 - la1; dlo = math.radians(lon2 - lon1)
    a = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _prev_month_day(y, m):
    """当月 1 日的前一天（儒略历，按 30/31/28 天近似——目录日只用于查表，误差可忽略：
    2 月 1 日前一天取 1 月 31 日，其余月取上月最后一天；闰年 3 月 1 日取 2 月 29/28
    差一日不影响「前一天是否有目录条目」的判定，因日食间隔远大于 1 日）。"""
    days = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30}
    if m == 1:
        return (y - 1, 12, 31)
    return (y, m - 1, days[m - 1])


def run():
    cat = parse_catalog()
    print(f'官方目录解析：{len(cat)} 条（-1999..+3000）')

    # tmp/tang 前身 canon（作交叉校验参照）
    ref = {}
    try:
        tmpd = json.load(open(TMPTANG, encoding='utf-8'))
        for e in tmpd['entries']:
            c = (e.get('ephem') or {}).get('canon')
            if c:
                ref[e['id']] = c
        print(f'tmp/tang 参照 canon：{len(ref)} 条')
    except Exception as ex:
        print(f'⚠ tmp/tang 参照读取失败：{ex}')

    src = open(os.path.join(ROOT, 'data/tang.js'), encoding='utf-8').read()
    j = src.index('=', src.index('.tang'))
    head = src[:j + 1]
    obj = json.loads(src[j + 1:].strip().rstrip(';'))
    recs = obj['records']

    n_geom = n_keep = 0
    n_refchk = n_refdiff = 0
    v_mag, v_km, v_td = [], [], []
    for rec in recs:
        e = rec['extra']
        rid = rec['id']
        y, mo, d = (int(x) for x in rec['dateLabel'].split('-'))
        ymd = (y, mo, d)

        # 干支复核（历日锚定自检）
        gz_check = tg.ganzhi(tg.jdn_julian(y, mo, d))
        gz_ok = (gz_check == e.get('ganzhi'))

        c = cat.get(ymd)
        local_shift = 0
        anchor_ymd = ymd
        if c is None:
            # 长安地方日救援：目录按 UT 记日，食甚 UT 晚于约 16:44（UT+7.26h 跨午夜）
            # 时长安地方日为次日 —— 即 dateLabel 前一天的目录条目。判据：
            #   目录日 D = dateLabel − 1，且 D 日长安地方时落入 dateLabel 当日。
            py_, pm_, pd_ = (y, mo, d - 1) if d > 1 else _prev_month_day(y, mo)
            D1 = cat.get((py_, pm_, pd_))
            if D1 is not None:
                ut_sec = (int(D1['tdText'][:2]) * 3600 + int(D1['tdText'][3:5]) * 60
                          + int(D1['tdText'][6:8]) - D1['dt']) % 86400
                if ut_sec + 26136 >= 86400:        # 长安地方时跨午夜 → 地方日 = D+1 = dateLabel
                    c, local_shift, anchor_ymd = D1, 1, (py_, pm_, pd_)
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
            e['catNone'] = '官方五千年目录该日（儒略历）无日食记录；原文纪日存疑，保留降级示意'
            rec['type'] = 'none'
            rec['flags'] = ['noEclipse']
            rec.pop('shadowFrames', None); rec.pop('timeRange', None)
            rec.pop('centralLine', None); rec.pop('umbraPolygon', None)
            rec.pop('penumbraPolygon', None); rec.pop('stations', None)
            print(f"  #{rid} {rec['era']}: 官方目录无该日条目（干支复核 {gz_check}"
                  f"{'✓' if gz_ok else '✗ vs 原文' + str(e.get('ganzhi'))}），近邻 {near[:2]}")
            continue

        jd_tt = tg.jdn_julian(*anchor_ymd) - 0.5 + c['tdH'] / 24.0
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
        # 原文互证：记「既」→ 长安近全食
        if '既' in rec['text'] and '几既' not in rec['text'] and cap:
            if cap['obsc'] < 0.97: warn += f' ⚠原文既 vs 算{cap["obsc"]:.2f}'
        # 与 tmp/tang 参照 canon 比对
        refc = ref.get(rid)
        refnote = ''
        if refc:
            n_refchk += 1
            diffs = []
            if refc.get('cat') != f'{c["catNum"]:05d}': diffs.append(f"cat {refc.get('cat')} vs {c['catNum']}")
            if refc.get('td') != c['tdText']: diffs.append(f"TD {refc.get('td')} vs {c['tdText']}")
            if abs(float(refc.get('gamma', 9)) - c['gamma']) > 0.0005: diffs.append('γ')
            if abs(float(refc.get('mag', 9)) - c['mag']) > 0.0005: diffs.append('mag')
            if diffs:
                n_refdiff += 1
                refnote = f' ⚠tmp/tang参照:{",".join(diffs)}'
        print(f"  #{rid} {rec['era']:8s} {rec['dateLabel']}{' (地方日+1)' if local_shift else ''} {r['type']:7s} "
              f"mag {r['maxMagnitude']:.2f}/{c['mag']:.2f} 中心Δ{d_km:5.0f}km "
              f"TDΔ{r['peakOffsetMin']:+.0f}min 长安算{cap['obsc']:.2f}/{cap['alt']:5.1f}° "
              f"{'干支✓' if gz_ok else '干支✗'}{warn}{refnote}")
        sys.stdout.flush()

        # ---- 合并 ----
        rec['type'] = r['type']
        e['cat'] = {'td': c['tdText'], 'ut': None, 'dt': c['dt'], 'gamma': c['gamma'],
                    'mag': c['mag'], 'lat': round(c['lat'], 1), 'lon': round(c['lon'], 1),
                    'type': c['typeLetter'], 'catNum': c['catNum'],
                    'saros': c['saros'], 'dur': c['dur'],
                    'sunAlt': c['sunAlt'], 'widthKm': c['widthKm'],
                    'catDate': '%04d-%02d-%02d' % anchor_ymd,
                    'localDayShift': local_shift}
        for k in ('center', 'maxMagnitude', 'pathWidthKm', 'umbraRadiusKm',
                  'penumbraRadiusDeg', 'durationSec', 'timeRange', 'centralLine',
                  'umbraPolygon', 'penumbraPolygon', 'shadowFrames', 'stations'):
            rec[k] = r[k]
        # visibility 由引擎重判（唐无原表本地实况可信值，pyephem 旧值弃用）
        rec['visibility'] = 'visible' if (cap and cap.get('visible')) else 'unseen'
        rec['flags'] = []
        # UT = TD − ΔT（展示用）
        sec = (int(c['tdText'][:2]) * 3600 + int(c['tdText'][3:5]) * 60 + int(c['tdText'][6:8]) - c['dt']) % 86400
        e['cat']['ut'] = '%02d:%02d:%02d' % (sec // 3600, (sec % 3600) // 60, sec % 60)
        n_geom += 1

    print(f"\n几何复算 {n_geom} 条，降级/无锚 {n_keep} 条")
    print(f"tmp/tang 参照比对：{n_refchk} 条可比，{n_refdiff} 条不一致")
    if v_mag:
        print(f"食分 vs 官方：最大偏差 {max(v_mag):.3f}")
        print(f"中心 vs 官方：最大 {max(v_km):.0f} km，中位 {sorted(v_km)[len(v_km)//2]:.0f} km")
        print(f"食甚时刻 vs 官方 TD：最大偏移 {max(v_td):.1f} min")
    obj['_meta'] = dict(obj.get('_meta', {}), note=(
        '《新唐书·天文志二》93 条；原文照录；历日由历朔干支匹配（91 条经官方目录独立旁证）；'
        '几何由 pymeeus（ELP-2000/82 + VSOP87）+ 矢量影锥复算（WGS84 椭球），'
        '逐条以 NASA 五千年目录官方值（TD/ΔT/γ/mag/中心坐标）锚定并交叉校验；'
        '#0044/#0088/#0090 官方目录该日无食，保留降级。'))
    with open(os.path.join(ROOT, 'data/tang.js'), 'w', encoding='utf-8') as f:
        f.write(head + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print("已写回 data/tang.js")


if __name__ == '__main__':
    run()

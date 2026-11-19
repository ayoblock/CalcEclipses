#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两晋日食重建（tools/build_jin_geom.py）—— 按汉/唐统一管线

输入：
  · tmp/jin/两晋古籍日食记录表.csv（60 条史料字段：年号年/农历月/lunarGanZhi/
    原文摘要/出处/观测地点/宿度分野/校勘备注/占辞）
  · tmp/jin/jin_eclipse.json（旧管线换算日期，仅作干支定日的邻域提示）
  · tmp/5MKSEcatalog.txt（NASA 五千年官方目录，逐条锚定）

流程：
  1. 年号 → 年（西晋/东晋年号表分列消歧），月相朔晦与干支取自 lunarGanZhi；
  2. 干支独立定日：在旧换算日 ±45 日窗口取最近干支日（60 日一循环，
     ±45 日窗口内至多 2 个候选，取最近者），与旧管线换算相差 >1 日则记录；
  3. 官方目录锚定：目录日 = 干支日；食甚 UT 过晚跨午夜时地方日 = 目录日 + 1，
     救援目录前一日条目（偏移按观测地经度：洛阳 26988s / 建康 28510s / 长安 26136s）；
  4. 目录无食 → 降级（晋书两晋日食多系历官推步所记，如实标注「目录无食 · 存疑」，
     给出 ±45 日内最近目录条目作近邻参考）；
  5. pymeeus 复算（与汉/唐同款 build_tang_geom 引擎），质量校验后合并出 data/jin.js。

与旧管线（tmp/jin erfa 后端）的差异：
  · 旧管线 24 条判「不入食限（推步虚报）」；本管线以官方目录逐条裁决，
    目录命中者给真实几何，未命中者保留降级并给近邻。
  · 旧管线 21 条换算日与干支纪日 ±1～6 日不合；本管线以干支纪日为权威独立定日。
"""
import csv, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tang_geom as tg
from rebuild_tang_geom import parse_catalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, 'tmp/jin/两晋古籍日食记录表.csv')
OLD = os.path.join(ROOT, 'tmp/jin/jin_eclipse.json')

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 年号 → 元年（公历年份）。西晋/东晋分列以消歧（建武 304/317、永熙 290 等）
ERA_W = [("泰始", 265), ("咸宁", 275), ("太康", 280), ("太熙", 290),
         ("永平", 291), ("元康", 291), ("永康", 300), ("永宁", 301),
         ("太安", 302), ("永安", 304), ("建武", 304), ("永兴", 304),
         ("光熙", 306), ("永嘉", 307), ("建兴", 313)]
ERA_E = [("建武", 317), ("太兴", 318), ("永昌", 322), ("太宁", 323),
         ("咸和", 326), ("咸康", 335), ("建元", 343), ("永和", 345),
         ("升平", 357), ("隆和", 362), ("兴宁", 363), ("太和", 366),
         ("咸安", 371), ("宁康", 373), ("太元", 376), ("隆安", 397),
         ("元兴", 402), ("义熙", 405), ("元熙", 419)]

# 观测地（旧管线坐标口径）
SITES = {
    "洛阳": {"lon": 112.45, "lat": 34.62},
    "建康": {"lon": 118.78, "lat": 32.04},
    "长安": {"lon": 108.94, "lat": 34.34},
}

CN_NUM = {"元": 1, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def cn_num(s):
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in CN_NUM:
        return CN_NUM[s]
    if "十" in s:
        a, _, b = s.partition("十")
        return (CN_NUM.get(a, 1) if a else 1) * 10 + (CN_NUM.get(b, 0) if b else 0)
    return 1


def gz_index(s):
    for i in range(60):
        if GAN[i % 10] == s[0] and ZHI[i % 12] == s[1]:
            return i
    raise ValueError("非法干支：" + s)


def era_year(text, dynasty):
    """「泰始二年七月丙午晦」→ ('泰始二年', 266, '七月丙午晦')
    两晋年号均为二字；年序为 元/一~十/二十。"""
    m = re.match(r'^([\u4e00-\u9fff]{2})((?:二十|[元一二三四五六七八九十])+?)年(.*)$', text)
    if not m:
        raise ValueError("年号年解析失败：" + text)
    era, n, rest = m.group(1), m.group(2), m.group(3)
    # 西晋/东晋年号表分列；唯一重名年号「建武」按 dynasty 消歧（304 西晋 / 317 东晋）。
    # 建兴五年（317）属西晋之末（愍帝纪年仍在江南沿用），归西晋表。
    if era == '建武' and dynasty == '东晋':
        table = ERA_E
    else:
        table = ERA_W
        start = next((y for (nm, y) in table if nm == era), None)
        if start is None:
            table = ERA_E
    start = next((y for (nm, y) in table if nm == era), None)
    if start is None:
        raise ValueError("未知年号：%s（%s）" % (era, dynasty))
    return f"{era}{n}年", start + cn_num(n) - 1, rest


def month_of(rest):
    m = re.match(r'^((闰)?[正一二三四五六七八九十]{1,2})月', rest)
    return m.group(1) if m else ''


def load_csv():
    rows = []
    with open(CSV, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def run():
    cat = parse_catalog()
    print(f"官方目录解析：{len(cat)} 条")
    old = {r['id']: r for r in json.load(open(OLD, encoding='utf-8'))['eclipses']}
    rows = load_csv()
    print(f"CSV 条目：{len(rows)} 条")

    records = []
    n_hit = n_shift = n_miss = 0
    v_mag, v_km, v_td = [], [], []
    for idx, row in enumerate(rows, 1):
        rid = '%04d' % idx
        oldr = old[row['id']]
        dynasty = oldr['dynasty']                     # 西晋 / 东晋
        label, gyear, rest = era_year(row['年号年'], dynasty)
        lgz = row['lunarGanZhi']
        gz = re.search(r'([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])', lgz).group(1)
        phase = '朔' if lgz.endswith('朔') else ('晦' if lgz.endswith('晦') else '')
        site_name = row['观测地点'] or oldr['observePlaces'][0]['name']
        site = SITES[site_name]

        # ---- 干支独立定日：旧换算日 ±45 日窗口取最近干支日 ----
        oy, om, od = (int(x) for x in oldr['convertDate'].split('（')[0].split('-'))
        jdn0 = tg.jdn_julian(oy, om, od)
        want = gz_index(gz)
        cands = [jdn0 + dj for dj in range(-45, 46) if (jdn0 + dj + 49) % 60 == want]
        if not cands:
            raise RuntimeError(f"{rid} 干支日无解：{lgz}")
        jdn = min(cands, key=lambda x: abs(x - jdn0))
        y, mo, d = tg.jdn_to_julian(jdn)
        # 年序一致性：干支日应落在年号年（十一月/十二月可跨至次年）
        if y not in (gyear, gyear + 1):
            print(f"  ⚠ {rid} {label} 干支日 {y}-{mo:02d}-{d:02d} 与年号年 {gyear} 不合")
        d_off = jdn - jdn0
        date_label = '%04d-%02d-%02d' % (y, mo, d)
        date_method = '干支纪日独立定日（±45 日窗口取最近干支日）'
        if d_off:
            date_method += f'；与旧管线换算相差 {d_off:+d} 日'

        # ---- 官方目录锚定 ----
        station = {"name": site_name, "lon": site['lon'], "lat": site['lat']}
        c = cat.get((y, mo, d))
        local_shift = 0
        anchor_ymd = (y, mo, d)
        if c is None:
            # 地方日救援：目录按 UT 记日；食甚 UT 过晚则地方日 = 目录日 + 1
            py_, pm_, pd_ = (y, mo, d - 1) if d > 1 else (y - 1, 12, 31)
            D1 = cat.get((py_, pm_, pd_))
            off_sec = int(site['lon'] / 15 * 3600)
            if D1 is not None:
                ut_sec = (int(D1['tdText'][:2]) * 3600 + int(D1['tdText'][3:5]) * 60
                          + int(D1['tdText'][6:8]) - D1['dt']) % 86400
                if ut_sec + off_sec >= 86400:
                    c, local_shift, anchor_ymd = D1, 1, (py_, pm_, pd_)

        rec = {
            "id": rid, "sortKey": jdn, "dateLabel": date_label,
            "era": label, "lunarDate": lgz, "dynastyLabel": dynasty,
            "source": row['出处'], "text": row['原文摘要'],
            "flags": [], "visibility": 'unseen',
            "center": {"lon": None, "lat": None, "alt": None},
            "stations": [station],
            "maxMagnitude": 0, "pathWidthKm": 0, "umbraRadiusKm": 0,
            "penumbraRadiusDeg": 0, "durationSec": 0,
            "centralLine": [], "umbraPolygon": [], "penumbraPolygon": [],
            "shadowFrames": [],
        }
        gz_self = tg.ganzhi(jdn)                      # 构造自检，必合
        assert gz_self == gz, (rid, gz_self, gz)
        e = rec['extra'] = {
            "jdn": jdn, "ganzhi": gz, "phase": phase, "lunarMonth": month_of(rest),
            "mansion": row['宿度分野'] or None,
            "omen": row['占辞'] or None,
            "variant": row['校勘备注'] or None,
            "tableText": '几既' if '几既' in row['原文摘要'] else '日有食之',
            "dateMethod": date_method,
            "match": '干支吻合（独立定日）',
        }

        if c is None:
            n_miss += 1
            near = []
            for (cy, cm, cd), cc in cat.items():
                dd = tg.jdn_julian(cy, cm, cd) - jdn
                if abs(dd) <= 45:
                    near.append({'date': '%04d-%02d-%02d' % (cy, cm, cd),
                                 'type': cc['typeLetter'], 'mag': cc['mag'],
                                 'off': int(dd)})
            near.sort(key=lambda x: abs(x['off']))
            e['catNear'] = near[:3]
            e['catNone'] = ('官方五千年目录该日（儒略历）无日食记录；两晋日食多系历官推步所记，'
                            '或为推步虚报、或为月序/干支传讹，保留降级示意')
            rec['type'] = 'none'
            rec['flags'] = ['noEclipse']
            # 站点保留历史观测地（visible=null：目录无食，不作「地平线下」判定）
            rec['stations'] = [{"name": site_name, "lon": site['lon'],
                                "lat": site['lat'], "visible": None}]
            print(f"  #{rid} {label} {lgz} {date_label}: 目录无食（旧管={'虚报' if oldr.get('isNoEat') else '有食'}）"
                  f" 近邻 {[(x['date'], round(x['off'])) for x in near[:2]]}")
            records.append(rec)
            continue

        (n_hit, n_shift) = (n_hit + 1, n_shift + local_shift)
        jd_tt = tg.jdn_julian(*anchor_ymd) - 0.5 + c['tdH'] / 24.0
        tg.STATIONS = [station]
        r = tg.compute_eclipse(jd_tt, window_min=180, dt_s=c['dt'])
        if r is None:
            n_miss += 1
            e['recheck'] = '官方目录有食但引擎复算未见（需人工核查）'
            print(f"  #{rid} {label}: ⚠ 引擎复算无食！")
            records.append(rec)
            continue

        # ---- 质量校验 ----
        def hav_km(la1, lo1, la2, lo2):
            p1, p2 = math.radians(la1), math.radians(la2)
            dla = p2 - p1; dlo = math.radians(lo2 - lo1)
            a = math.sin(dla / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlo / 2) ** 2
            return 2 * 6371.0 * math.asin(math.sqrt(a))
        d_km = hav_km(r['center']['lat'], r['center']['lon'], c['lat'], c['lon'])
        v_mag.append(abs(r['maxMagnitude'] - c['mag']))
        v_km.append(d_km)
        v_td.append(abs(r['peakOffsetMin']))
        warn = ''
        if d_km > 150: warn += ' ⚠中心偏差'
        if abs(r['maxMagnitude'] - c['mag']) > 0.02: warn += ' ⚠食分偏差'
        if abs(r['peakOffsetMin']) > 5: warn += ' ⚠时刻偏差'
        print(f"  #{rid} {label} {lgz} {date_label}{' (地方日+1)' if local_shift else ''} "
              f"{r['type']:7s} mag {r['maxMagnitude']:.2f}/{c['mag']:.2f} 中心Δ{d_km:4.0f}km "
              f"TDΔ{r['peakOffsetMin']:+.0f}min {site_name}算{r['stations'][0]['obsc']:.2f}/{r['stations'][0]['alt']:5.1f}°{warn}")
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
        sec = (int(c['tdText'][:2]) * 3600 + int(c['tdText'][3:5]) * 60
               + int(c['tdText'][6:8]) - c['dt']) % 86400
        e['cat']['ut'] = '%02d:%02d:%02d' % (sec // 3600, (sec % 3600) // 60, sec % 60)
        for k in ('center', 'maxMagnitude', 'pathWidthKm', 'umbraRadiusKm',
                  'penumbraRadiusDeg', 'durationSec', 'timeRange', 'centralLine',
                  'umbraPolygon', 'penumbraPolygon', 'shadowFrames', 'stations'):
            rec[k] = r[k]
        rec['visibility'] = 'visible' if r['stations'][0].get('visible') else 'unseen'
        records.append(rec)

    print(f"\n目录命中 {n_hit}（含地方日救援 {n_shift}），降级/无锚 {n_miss}")
    if v_mag:
        print(f"食分 vs 官方：最大偏差 {max(v_mag):.3f}")
        print(f"中心 vs 官方：最大 {max(v_km):.0f} km，中位 {sorted(v_km)[len(v_km)//2]:.0f} km")
        print(f"食甚时刻 vs 官方 TD：最大偏移 {max(v_td):.1f} min")

    obj = {
        "_meta": {
            "schema": 1, "key": "jin", "label": "两晋日食",
            "note": ("《晋书·天文志》两晋日食 60 条；原文照录；历日由干支纪日独立定日"
                     "（旧管线 21 条换算与干支不合，已重定）；几何由 pymeeus（ELP-2000/82 + VSOP87）"
                     "+ 矢量影锥复算（WGS84 椭球），逐条以 NASA 五千年目录官方值锚定并交叉校验；"
                     "目录无食条目为晋书推步记录特性，如实降级标注。"),
        },
        "records": records,
    }
    with open(os.path.join(ROOT, 'data/jin.js'), 'w', encoding='utf-8') as f:
        f.write('window.__ECLIPSE_DATA__ = window.__ECLIPSE_DATA__ || {};\n')
        f.write('window.__ECLIPSE_DATA__.jin =')
        f.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')))
        f.write(';\n')
    print("已写出 data/jin.js")


if __name__ == '__main__':
    run()

# -*- coding: utf-8 -*-
"""
一次性迁移脚本：把旧的「历 - 汉日食.html」「历 - 宋日食.html」内联数据
转换为统一 schema，输出 data/*.js（挂到 window.__ECLIPSE_DATA__）。

同时抽取宋版底图纹理到 js/assets.js。

运行： python3 tools/normalize.py
（本脚本只在首次搭建工程时需要；后续新增朝代直接按 data/_template.js 写数据即可。）
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DHTML = os.path.join(ROOT, "历 - 汉日食.html")
SONG_HTML = os.path.join(ROOT, "历 - 宋日食.html")
SONG_JSON = os.path.join(ROOT, "eclipse_data.json")
DATA_DIR = os.path.join(ROOT, "data")
JS_DIR = os.path.join(ROOT, "js")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(JS_DIR, exist_ok=True)

TYPE_MAP_CN = {"全食": "total", "环食": "annular", "偏食": "partial", "无对应": "none"}
HAN_SUB_FLAGS = {
    "noecl": ["noEclipse"],
    "nolat": ["notAtStation"],
    "below": ["belowHorizon"],
    "visible": [],
}


def dump_js(varname, obj):
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return ("window.__ECLIPSE_DATA__ = window.__ECLIPSE_DATA__ || {};\n"
            "window.__ECLIPSE_DATA__.%s = %s;\n" % (varname, payload))


# ---------------- 汉 ----------------
s = open(DHTML, encoding="utf-8").read()
han_raw = json.loads(re.search(r"const DATA\s*=\s*(\[.*?\]);", s, re.S).group(1))

han_records = []
for e in han_raw:
    st = e.get("sub", "visible")
    han_records.append({
        "id": str(e["id"]),
        "sortKey": e.get("jd", 0),
        "dateLabel": e.get("date_cn", ""),
        "dateRaw": e.get("date", ""),
        "era": e.get("era", ""),
        "lunarDate": "",
        "dynastyLabel": "西汉",
        "source": "《汉书·五行志下之下》",
        "text": e.get("text", ""),
        "type": e.get("cls", "none"),
        "flags": HAN_SUB_FLAGS.get(st, []),
        "visibility": st,
        "center": {"lon": e.get("slon", 0), "lat": e.get("slat", 0)},
        "stations": [{
            "name": "长安", "lon": 108.9, "lat": 34.3,
            "visible": st == "visible",
            "obsc": e.get("mag", 0),
            "alt": e.get("alt", 0),
        }],
        "extra": {
            "jd": e.get("jd"), "off": e.get("off"), "mag": e.get("mag"),
            "alt": e.get("alt"), "mag_geo": e.get("mag_geo"), "alt_geo": e.get("alt_geo"),
            "alt_ecl": e.get("alt_ecl"), "instant": e.get("instant"),
            "gsep": e.get("gsep"), "total": e.get("total"), "paper": e.get("paper"),
            "paper_mag": e.get("paper_mag"), "near": e.get("near"), "sub": st,
        },
    })

han_pack = {
    "_meta": {
        "schema": 1,
        "key": "han",
        "label": "汉书五行志",
        "note": "54 条；仅含影心点与食分标量，无中心线/影带/逐帧，采用点位降级渲染。",
    },
    "records": han_records,
}
open(os.path.join(DATA_DIR, "han.js"), "w", encoding="utf-8").write(dump_js("han", han_pack))

# ---------------- 宋 ----------------
song_raw = json.load(open(SONG_JSON, encoding="utf-8"))["records"]

song_records = []
for rec in song_raw:
    flags = []
    if rec.get("isCloudHide"):
        flags.append("cloudHide")
    if rec.get("isNoEat"):
        flags.append("noEat")
    if rec.get("localUnseen"):
        flags.append("localUnseen")
    stype = rec.get("solarType", "")
    song_records.append({
        "id": str(rec.get("id", "")),
        "sortKey": int(str(rec.get("julianDate", "0000-00-00")).replace("-", "")),
        "dateLabel": rec.get("julianDate", ""),
        "dateRaw": rec.get("julianDate", ""),
        "era": rec.get("yearName", ""),
        "lunarDate": rec.get("lunarDate", ""),
        "dynastyLabel": rec.get("dynasty", ""),
        "source": rec.get("source", ""),
        "text": rec.get("originalText", ""),
        "type": TYPE_MAP_CN.get(stype, "none"),
        "flags": flags,
        "visibility": "visible",
        "center": rec.get("center"),
        "centralLine": rec.get("centralLine"),
        "umbraPolygon": rec.get("umbraPolygon"),
        "penumbraPolygon": rec.get("penumbraPolygon"),
        "shadowFrames": rec.get("shadowFrames"),
        "timeRange": rec.get("timeRange"),
        "maxMagnitude": rec.get("maxMagnitude"),
        "pathWidthKm": rec.get("pathWidthKm"),
        "umbraRadiusKm": rec.get("umbraRadiusKm"),
        "penumbraRadiusDeg": rec.get("penumbraRadiusDeg"),
        "durationSec": rec.get("durationSec"),
        "stations": rec.get("recordPoints", []),
        "extra": {
            "nasaId": rec.get("nasaId"), "remark": rec.get("remark"),
            "solarTypeRaw": stype,
        },
    })

song_pack = {
    "_meta": {
        "schema": 1,
        "key": "song",
        "label": "两宋日食",
        "note": "225 条；含中心线/本影半影多边形/逐帧月影，完整几何渲染。",
    },
    "records": song_records,
}
open(os.path.join(DATA_DIR, "song.js"), "w", encoding="utf-8").write(dump_js("song", song_pack))

# ---------------- 底图纹理 ----------------
m = re.search(r"const LAND_TEX\s*=\s*'([^']+)'", s if False else open(SONG_HTML, encoding="utf-8").read())
if m:
    open(os.path.join(JS_DIR, "assets.js"), "w", encoding="utf-8").write(
        "window.__LAND_TEX__ = '%s';\n" % m.group(1)
    )
    print("assets.js 写出，纹理长度", len(m.group(1)))
else:
    open(os.path.join(JS_DIR, "assets.js"), "w", encoding="utf-8").write(
        "window.__LAND_TEX__ = '';\n")
    print("警告：未找到 LAND_TEX，底纹将留空")

print("汉 %d 条 -> data/han.js" % len(han_records))
print("宋 %d 条 -> data/song.js" % len(song_records))

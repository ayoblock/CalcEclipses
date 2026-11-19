# -*- coding: utf-8 -*-
"""
宋朝原文补入脚本：用补全原文版的 tmp/eclipse_data.json 重建 data/song.js。

背景
----
data/song.js 是早期由 normalize.py 从旧 eclipse_data.json 生成的，
225 条里 224 条 text/source/lunarDate 是占位符。
tmp/eclipse_data.json 是同源天文数据（按公历日对齐后，几何字段 218/218 一致）
但补齐了原文（originalText）、出处、历日干支的补全版。

本脚本复用 normalize.py 的宋版字段映射逻辑，把补全版重新生成为 song.js，
使原文/出处/历日进入前端，同时：
  - 保留全部几何字段（中心线/本影半影多边形/逐帧/时段，原样照搬）
  - 修正 flags：按 isCloudHide/isNoEat/localUnseen 三旗标映射（旧版只映射了后者）
  - 清理过时 remark：「古籍出处、干支与原文待补」在出处/干支/原文均已补入后
    改写为如实描述，其余 remark 原样保留
  - 不编造任何原文：originalText 里本就标「（无原记，依朔望回推补入）」的
    108 条如实保留占位说明

运行： python3 tools/restore_song_text.py
输入： tmp/eclipse_data.json
输出： data/song.js
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tmp", "eclipse_data.json")
OUT = os.path.join(ROOT, "data", "song.js")

TYPE_MAP_CN = {
    "全食": "total", "环食": "annular", "偏食": "partial",
    "全环食": "hybrid", "无对应": "none",
}

# 过时 remark 的固定前缀 + 需替换的过时短语
STALE_PREFIX = "天文回推条目"
STALE_PHRASE = "古籍出处、干支与原文待补"


def fix_remark(remark, text):
    """原文已补入时，修正 remark 中过时的「待补」表述。"""
    rm = str(remark or "")
    if STALE_PREFIX in rm and STALE_PHRASE in rm:
        has_real = text and "待" not in text and "无原记" not in text
        if has_real:
            # 原文/出处/干支均已据古籍补入，仅几何仍为回推示意
            rm = rm.replace(
                "天文回推条目：古籍出处、干支与原文待补；本条按",
                "原文与出处、干支已据《宋史·天文志》补入；本条几何按",
            )
        else:
            # 仍为无原记条目：出处与历日已标注为回推，说明保留但改述
            rm = rm.replace(
                "天文回推条目：古籍出处、干支与原文待补；本条按",
                "天文回推条目：古籍无对应原记，出处与历日据朔望回推补入；本条按",
            )
    return rm


def iso4(t):
    """把 ISO 时间串的年份补零到 4 位：'960-05-28T03:39:59Z' → '0960-05-28T03:39:59Z'。

    Cesium 的 JulianDate.fromIso8601 要求 4 位年份；宋代早期（960–999）源数据
    是 3 位年份，解析失败会返回无效 JulianDate，导致 shadowAt 里 secondsDifference
    得 NaN、f[NaN] 为 undefined，最终抛 'can't access property lon' 并中断渲染。
    dateLabel 不进 Cesium（仅显示/搜索），保持原样以免影响 initialRecord 匹配。
    """
    if not t:
        return t
    return re.sub(r"^(\d{1,3})-", lambda m: m.group(1).zfill(4) + "-", str(t))


def flatten_pairs(value):
    """把 [[lon,lat], ...] 的嵌套坐标扁平化为 [lon,lat, ...]。

    源 JSON 里多边形字段存在两种格式混杂：多数是扁平数组（Cesium
    Cartesian3.fromDegreesArray 的期望输入），少数批次（8 条）是嵌套数组。
    app.js 对 polygon 未做 flat，嵌套格式会导致 fromDegreesArray 的
    "Invalid array length" 报错。此处统一为扁平格式；已是扁平的原样返回。
    """
    if not isinstance(value, list) or not value:
        return value
    if isinstance(value[0], list):
        return [coord for pair in value for coord in pair]
    return value


def dump_js(varname, obj):
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return ("window.__ECLIPSE_DATA__ = window.__ECLIPSE_DATA__ || {};\n"
            "window.__ECLIPSE_DATA__.%s = %s;\n" % (varname, payload))


def main():
    raw = json.load(open(SRC, encoding="utf-8"))["records"]

    records = []
    stat = {"total": 0, "real_text": 0, "no_record": 0,
            "remark_fixed": 0, "poly_flattened": 0, "iso_fixed": 0,
            "cloud": 0, "noeat": 0, "localunseen": 0}
    for r in raw:
        text = r.get("originalText", "")
        flags = []
        if r.get("isCloudHide"):
            flags.append("cloudHide")
            stat["cloud"] += 1
        if r.get("isNoEat"):
            flags.append("noEat")
            stat["noeat"] += 1
        if r.get("localUnseen"):
            flags.append("localUnseen")
            stat["localunseen"] += 1

        stype = r.get("solarType", "")
        remark = fix_remark(r.get("remark"), text)
        if remark != str(r.get("remark") or ""):
            stat["remark_fixed"] += 1

        umbra_raw = r.get("umbraPolygon")
        penumbra_raw = r.get("penumbraPolygon")
        if isinstance(umbra_raw, list) and umbra_raw and isinstance(umbra_raw[0], list):
            stat["poly_flattened"] += 1
        if isinstance(penumbra_raw, list) and penumbra_raw and isinstance(penumbra_raw[0], list):
            stat["poly_flattened"] += 1

        if text and "待" not in text and "无原记" not in text:
            stat["real_text"] += 1
        if "无原记" in text:
            stat["no_record"] += 1

        # 时间串补零到 4 位年份（Cesium fromIso8601 要求），根治 960–999 年
        # 条目解析失败导致的渲染中断。dateLabel/dateRaw 不动（仅供显示/搜索）。
        shadow_frames = r.get("shadowFrames")
        if shadow_frames:
            shadow_frames = [dict(fr, t=iso4(fr.get("t"))) if isinstance(fr, dict) and fr.get("t") else fr
                             for fr in shadow_frames]
            stat["iso_fixed"] += 1
        time_range = r.get("timeRange")
        if time_range:
            time_range = {k: iso4(v) if k in ("start", "maxEclipse", "end") else v
                          for k, v in time_range.items()}
            stat["iso_fixed"] += 1

        jd = str(r.get("julianDate", "0000-00-00"))
        records.append({
            "id": str(r.get("id", "")),
            "sortKey": int(jd.replace("-", "")),
            "dateLabel": jd,
            "dateRaw": jd,
            "era": r.get("yearName", ""),
            "lunarDate": r.get("lunarDate", ""),
            "dynastyLabel": r.get("dynasty", ""),
            "source": r.get("source", ""),
            "text": text,
            "type": TYPE_MAP_CN.get(stype, "none"),
            "flags": flags,
            "visibility": "visible",
            "center": r.get("center"),
            "centralLine": r.get("centralLine"),   # 嵌套坐标，app.js 用 .flat()
            "umbraPolygon": flatten_pairs(r.get("umbraPolygon")),
            "penumbraPolygon": flatten_pairs(r.get("penumbraPolygon")),
            "shadowFrames": shadow_frames,
            "timeRange": time_range,
            "maxMagnitude": r.get("maxMagnitude"),
            "pathWidthKm": r.get("pathWidthKm"),
            "umbraRadiusKm": r.get("umbraRadiusKm"),
            "penumbraRadiusDeg": r.get("penumbraRadiusDeg"),
            "durationSec": r.get("durationSec"),
            "stations": r.get("recordPoints", []),
            "extra": {
                "nasaId": r.get("nasaId"),
                "remark": remark,
                "solarTypeRaw": stype,
            },
        })
        stat["total"] += 1

    pack = {
        "_meta": {
            "schema": 1,
            "key": "song",
            "label": "两宋日食",
            "note": ("225 条；原文/出处/干支据《宋史·天文志》等补入，"
                     "无对应原记者如实标注；含中心线/本影半影多边形/逐帧月影，完整几何渲染。"),
        },
        "records": records,
    }
    open(OUT, "w", encoding="utf-8").write(dump_js("song", pack))
    print("写出 %s" % OUT)
    print("统计:", json.dumps(stat, ensure_ascii=False))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
就地修复 data/song.js 中进入 Cesium 的时间串：年份补零到 4 位。

背景
----
宋代早期（960–999）条目的 shadowFrames[].t 与 timeRange.* 是 3 位年份
（如 '960-05-28T03:39:59Z'），Cesium 的 JulianDate.fromIso8601 要求 4 位年份，
解析失败会让 shadowAt 里 secondsDifference 得 NaN、f[NaN]=undefined，
抛 "can't access property lon" 并中断整个渲染循环（Rendering has stopped）。

dateLabel/dateRaw 不进 Cesium（仅显示/搜索），保持原样以免影响 initialRecord
匹配与列表。本脚本幂等：已是 4 位的时间串不再改动。

运行： python3 tools/fix_song_iso_year.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "song.js")


def iso4(t):
    if not t:
        return t
    return re.sub(r"^(\d{1,3})-", lambda m: m.group(1).zfill(4) + "-", str(t))


def main():
    src = open(PATH, encoding="utf-8").read()
    i = src.index("=", src.index(".song"))
    prefix = src[:i + 1]          # window.__ECLIPSE_DATA__.song =
    payload = src[i + 1:].strip()
    if payload.endswith(";"):
        payload = payload[:-1]
    pack = json.loads(payload)

    fixed = 0
    for rec in pack["records"]:
        frames = rec.get("shadowFrames")
        if frames:
            for fr in frames:
                if isinstance(fr, dict) and fr.get("t"):
                    new = iso4(fr["t"])
                    if new != fr["t"]:
                        fr["t"] = new
                        fixed += 1
        tr = rec.get("timeRange")
        if tr:
            for k in ("start", "maxEclipse", "end"):
                if tr.get(k):
                    new = iso4(tr[k])
                    if new != tr[k]:
                        tr[k] = new
                        fixed += 1

    out = prefix + json.dumps(pack, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(PATH, "w", encoding="utf-8").write(out)
    print("修复时间串 %d 处 -> %s" % (fixed, PATH))


if __name__ == "__main__":
    main()

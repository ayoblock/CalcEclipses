"""严格自交检测：多边形任意两条不相邻边是否相交（球面近似为平面小尺度）。"""
import json, math, sys

def seg_cross(p1, p2, p3, p4):
    """规范线段相交判定（含共线重叠）。"""
    def d(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    d1 = d(p3, p4, p1); d2 = d(p3, p4, p2)
    d3 = d(p1, p2, p3); d4 = d(p1, p2, p4)
    if ((d1 > 1e-9 and d2 < -1e-9) or (d1 < -1e-9 and d2 > 1e-9)) and \
       ((d3 > 1e-9 and d4 < -1e-9) or (d3 < -1e-9 and d4 > 1e-9)):
        return True
    return False

def check(key):
    s = open(f'data/{key}.js', encoding='utf-8').read()
    j = s.index('=', s.index(f'.{key}'))
    recs = json.loads(s[j+1:].strip().rstrip(';'))['records']
    total, bad = 0, []
    for r in recs:
        up = r.get('umbraPolygon')
        if not up or len(up) < 10:
            continue
        total += 1
        pts = [(up[i], up[i+1]) for i in range(0, len(up)-1, 2)]
        n = len(pts)
        hits = 0
        for i in range(n):
            a1, a2 = pts[i], pts[(i+1) % n]
            for jj in range(i+2, n):
                if i == 0 and jj == n-1:
                    continue                    # 相邻闭合边
                b1, b2 = pts[jj], pts[(jj+1) % n]
                if seg_cross(a1, a2, b1, b2):
                    hits += 1
        if hits:
            bad.append((r['id'], hits))
    print(f'{key}: 检测 {total} 条本影带 | 自交条数 {len(bad)} {bad[:8]}')

if __name__ == '__main__':
    for k in ['han', 'jin', 'tang', 'song']:
        check(k)

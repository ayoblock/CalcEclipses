/* =====================================================================
   新朝代数据模板（字段规范 v1）
   ---------------------------------------------------------------------
   用法：
     1) 复制本文件为 data/<key>.js（例如 data/tang.js）
     2) 填好 _meta 与 records，改最后一行的 key 为你的朝代 key
     3) 在 index.html 的数据脚本区加一行 <script src="data/<key>.js"></script>
     4) 在 js/registry.js 的 DYNASTIES 数组追加一项配置（照 han/song 写）
   即可在界面顶栏看到新朝代按钮并完整切换。

   统一 schema 字段说明（records 数组每一项）：
   ── 必填 ──
   id           string   朝代内唯一编号，用于定位与 ?rec= 直达
   sortKey      number   排序键（建议用积日或 YYYYMMDD 数字），升序排列
   dateLabel    string   列表显示的日期文字，如 "前205年12月20日" / "960-05-28"
   era          string   纪年文字，如 "高帝三年" / "建隆元年"
   source       string   出处，如 "《汉书·五行志下之下》"
   text         string   古籍原文
   type         string   食型：'total' 全食 | 'annular' 环食 | 'partial' 偏食 | 'none' 无对应
   flags        string[] 标记，可取值：
                         'cloudHide' 云阴不见 | 'noEat' 当食不食 | 'localUnseen' 本地不见
                         'noEclipse' 全球无食 | 'notAtStation' 观测地不见 | 'belowHorizon' 地平线下
   visibility   string   'visible' 或其他；供 narrative 详情渲染判定
   center       {lon,lat,alt?}  食甚/影心中心经纬度（WGS84，lon 东经为正）
   stations     array    观测点：[{name,lon,lat,visible,obsc,alt,distKm?}]
                         visible 布尔；obsc 食分；alt 太阳高度
   extra        object   朝代专有字段，原样透传给详情渲染器
   ── 几何（可选，缺失则点位降级渲染）──
   centralLine   [[lon,lat],...]       食带中心线
   umbraPolygon  [lon,lat,lon,lat,...] 本影多边形（扁平数组）
   penumbraPolygon 同上                半影多边形
   shadowFrames  [{t,lon,lat,r,alt},...] 逐帧月影（t 为 ISO8601 UTC）
   timeRange     {start,maxEclipse,end} ISO8601 UTC，有则启用绝对时间轴
   maxMagnitude / pathWidthKm / umbraRadiusKm / penumbraRadiusDeg / durationSec  number
   ===================================================================== */

window.__ECLIPSE_DATA__ = window.__ECLIPSE_DATA__ || {};
window.__ECLIPSE_DATA__._template = {
  _meta: {
    schema: 1,
    key: '_template',
    label: '示例朝代',
    note: '这是模板占位数据，不会被注册到界面；复制后改成自己的 key。'
  },
  records: [
    {
      id: '0001',
      sortKey: 9600528,
      dateLabel: '960-05-28',
      dateRaw: '960-05-28',
      era: '建隆元年',
      lunarDate: '（待校）',
      dynastyLabel: '示例',
      source: '（待校）',
      text: '（原文待补）',
      type: 'annular',
      flags: [],
      visibility: 'visible',
      center: { lon: 93.2, lat: 20.29, alt: 87.9 },
      stations: [
        { name: '示例地点', lon: 114.3, lat: 34.8, visible: true, obsc: 0.65, alt: 54.7, distKm: 2635 }
      ],
      centralLine: [[47.67, -10.51], [93.2, 20.29], [146.18, 15.35]],
      umbraPolygon: [92.85, 19.48, 93.97, 19.85, 93.97, 20.6, 92.85, 19.48],
      penumbraPolygon: [91.0, -15.0, 129.5, 16.5, 118.0, 48.0, 61.5, 41.5, 91.0, -15.0],
      shadowFrames: [
        { t: '960-05-28T03:39:59Z', lon: 51.281, lat: -8.604, r: 8.0, alt: 14.7 },
        { t: '960-05-28T05:39:59Z', lon: 93.2, lat: 20.29, r: 6.0, alt: 87.9 }
      ],
      timeRange: { start: '960-05-28T03:03:59Z', maxEclipse: '960-05-28T05:33:59Z', end: '960-05-28T08:03:59Z' },
      maxMagnitude: 0.98,
      pathWidthKm: 254,
      umbraRadiusKm: 127,
      penumbraRadiusDeg: 0.9,
      durationSec: 320,
      extra: { nasaId: '', remark: '' }
    }
  ]
};

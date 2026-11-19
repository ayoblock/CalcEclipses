# 开发规范（内部）

> 面向贡献者/维护者的管线铁律与前端规范。项目整体定位见根 README（科普非专业）。
> 许可证 MIT（pymeeus 为 GPL-3.0，仅作为独立进程在 tools/ 中调用，不入前端分发）。

## 一、目录结构

```
CalcEclipses/
├─ index.html                 统一入口；数据脚本区按年代序引入 data/*.js
├─ run.sh / run.bat           一键启动（缺 Cesium 时分别调 fetch_cesium.sh/.ps1；
│                             sh 端口占用自动换空闲端口，bat 固定 8123）
├─ css/app.css                全局样式（暗底古铜）
├─ js/
│  ├─ registry.js             ★ 朝代注册表：按钮顺序、筛选、方法论弹窗、统计
│  ├─ calendar.js             ★ 历法推步：太初/泰始/大衍/纪元四历，干支纪日精确、月日近似
│  ├─ renderers.js            ★ 详情渲染器：各朝统一走 renderUnifiedDetail
│  ├─ app.js                  核心引擎：Cesium 图层、朝代切换、筛选、时间轴（含 BC 年 J() 直构）
│  └─ assets.js               底图纹理（内嵌 dataURI）
├─ data/                      各朝数据（window.__ECLIPSE_DATA__.<key>），_template.js 为字段规范
├─ lib/cesium/                Cesium 1.120 Build 产物（不入库；tools/fetch_cesium.sh 生成）
├─ tools/
│  ├─ build_tang_geom.py      ★ 核心引擎：pymeeus 星历 + 矢量影锥 + band_edges_from_contours
│  ├─ build_han_geom.py       汉管线：5MKSE 目录解析 + 锚定 + 复算（BC 年、6 位扩展 ISO）
│  ├─ rebuild_tang_geom.py    唐管线：NASA 目录锚定 + 长安地方日救援
│  ├─ build_jin_geom.py       晋管线：CSV 史料 + 干支独立定日 + 目录锚定
│  ├─ build_song_geom.py      宋管线：目录锚定 + ±1 日历日救援 + 开封/临安/开城三点
│  ├─ check_band_selfint.py   ★ 质量门：本影带 O(n²) 规范线段自交检测（han/jin/tang/song）
│  ├─ fetch_cesium.sh         一次性获取 lib/cesium（npm cesium@1.120）
│  └─ fetch_cesium.ps1        同上（Windows PowerShell 版，由 run.bat 调用）
└─ tmp/                       不入库：5MKSEcatalog.txt、前身实现、备份 *.bak_*、验证截图
```

`tmp/5MKSEcatalog.txt`（NASA Five Millennium Catalog 导出）不入仓库，重建数据管线时
需自行从 NASA 日食网站导出同名目录文件放入 `tmp/`。

## 二、数据管线规范（新增/重建朝代必须遵循）

**天文几何（不可变通）**：
1. 星历层一律 **pymeeus（ELP-2000/82 全项 + VSOP87）**；pyephem 在古代有 0.3°～1.8°
   月球黄经系统偏差（唐 ≈35min、西汉 ≈3.5h），已证实并弃用。
2. **逐条以 NASA 五千年目录（tmp/5MKSEcatalog.txt）锚定**：TD of greatest eclipse 为
   TT 锚、目录 ΔT 建地球自转角；目录值入 `extra.cat`（td/ut/dt/γ/食分/轴点/Saros/时长）。
3. 历日锚定三件套：**目录日直配 → 地方日救援**（食甚 UT 跨午夜时地方日 = 目录日+1，
   判据 `ut_sec + 站点经度偏移 ≥ 86400`，收编目录前一日条目）→ **±1 日历日存疑收编**
   （标注【历日存疑】旗标）。目录 ±1 日内无食者降级（type='none'、flags=['noEclipse']、
   给 catNear 近邻），**不补食、不编几何**。
4. 质量门（写进方法论 stats 前必须实测）：食分 vs NASA ≤0.05、影心偏差中位 <150 km、
   食甚时刻 ≤7 min、`check_band_selfint.py` 全朝 0 自交。

**历日定日（按史源分层）**：
- 原文有干支朔晦者：干支纪日是权威（连续纪日，`idx=(JDN+49) mod 60`）。晋管线示范
  「干支独立定日」（旧换算日 ±45 日窗口取最近干支日，年序与年号年互检）。
- 无原记者（宋 108 条）：**原记朔日锚点链插值**（历史月序权威，间距计数误差 <0.5 日；
  闰月按无中气置闰 + 边距排序；锚点链自检须 0 不符）。lunarDate 一律汉字月
  （「十月壬申朔」「闰三月」「晦」），禁数字月、禁「（待校）」、统一「闰」。
- 干支农历（lunarDate）一律从条目原文照录「`<月>月<干支><朔/晦>`」（先晦一日作
  「`<月>月<干支>（先晦一日）`」），原文权威、照录不改；原文干支与目录日不符属
  历日传讹，由判定层说明，不改写 lunarDate。**注意：月份正则字符类必须含「一」**
  （否则「十一月」全部漏配——曾踩坑）。

**历法推步卡（calendar.js）**：
- 常数取正史律历志原文（日法/朔实/岁分），注明出处与行用年代。
- **历元双职责解耦**：`epochJDN` = 真实冬至（气锚：节气/月序）、`shuoEpochJDN` =
  史载朔日实测校准的朔相位锚（残差 ±1.5 日为平朔 vs 定朔正常范围）。
- 推步卡是**独立参照列**：平朔月序与历史月序一致率 ~46–58% 是固有精度边界，
  必须随结果标注、与原文分行，不得混为定论。

## 三、前端规范

- **渲染器统一**：各朝详情一律 `renderUnifiedDetail`（宋式骨架），降级判定数据驱动
  （有 shadowFrames 或 timeRange.start 者走完整骨架）；朝代差异只进旗标/专有行。
- **观测地行**：不设「朝代」行，统一为「观测地：`<dynastyLabel>·<站点名>`」
  （如「西汉·长安」「北宋·开封、临安、开城」）；registry `stationName` 固定 '观测地'。
- **不静态渲染半影多边形**（扫掠包络/食甚落区跨数千公里叠暗色成大黑带）；
  半影信息由当前位置动态椭圆承担。静态本影带 + 中心线 + 发光轨迹 + 动态月影。
- **观测地简称用 `dynSite(dk, rec)`**（汉/唐=长安，晋=条目站点，宋=开封/临安）；
  目录 UT→地方时用 `catLocalTimeOff(cat, catLocalSite(dk, rec).off)`。
- **显示用词规范**（右侧面板与方法论弹窗）：
  - 「官方」一律写「NASA」——NASA 是 NASA，不是史书官方（「NASA 目录」「NASA TD」
    「NASA 食分」「NASA greatest eclipse」）；史书侧用「志文 / 原文 / 历官推步」表述。
    注意「NASA 五千年目录官方值」这类短语须改「NASA 五千年目录值」，避免双重替换。
  - 「儒略历」显示名一律写「中国公历」（换算日期括注「（中国公历）」）；
    代码注释中的儒略历口径表述不受此限。
  - 详情不设「干支纪日」行（推步卡已含日干支，不重复）；「中心线」行不写「NASA 目录锚定」。
- **BC 年时间**：Cesium 不支持负年 ISO，`app.js J()` 用儒略历 JDN 直构 JulianDate，
  `secondsOfDay` 从正午起算（12h 陷阱）；BC ISO 需 6 位扩展年（-000204）。
- Cesium **不得回退 CDN**（Workers 动态导入失败 → 渲染循环停止 → 全部图形消失）；
  仓库不含 lib/cesium，缺失时给出 `tools/fetch_cesium.sh` 指引。

## 四、新增朝代步骤

1. `data/<key>.js`：按 `data/_template.js` 字段规范（schema v1），由 tools/ 管线生成；
2. `index.html` 数据脚本区按年代序加一行；
3. `js/registry.js` DYNASTIES 按年代序插入配置（tabs/chips/searchFields/methodology/stats/footnote）；
4. 需要推步卡时 `js/calendar.js` CALENDARS 加历法常数 + `DYNASTY_CAL` 映射；
5. 跑质量门（`check_band_selfint.py` + Playwright 抽查条目/降级/回归），更新方法论统计。

## 五、验证方式

- `node --check js/*.js`；`python3 tools/check_band_selfint.py`；
- Playwright（本地静态服务）：逐朝载入、点降级条目、查
  `cesium-widget-errorPanel` 与 pageerror；截图确认影带/中心线/标记齐全。
  参考脚本 `tmp/verify_ui.py`（详情容器是 `#detail` 不是 `.detail`）。

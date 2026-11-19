/* =====================================================================
   朝代注册表 —— 统一的扩展入口
   ---------------------------------------------------------------------
   新增朝代只需两步：
     1) 在 data/ 下新建一个 xxx.js，形如
        window.__ECLIPSE_DATA__.xxx = { _meta:{...}, records:[ ... ] };
        （字段规范见 data/_template.js）
     2) 在下面 DYNASTIES 数组里追加一项配置，并在 index.html 中
        按需引入该 data/xxx.js（数据脚本）即可。
   界面顶栏按钮、筛选、详情、时间轴全部由这里的配置驱动。
   ===================================================================== */

const TYPE_LABEL = {
  total: '全食', annular: '环食', partial: '偏食', none: '无对应'
};
const TYPE_COLOR = {
  total: '#b8452f', annular: '#cfa03a', partial: '#4f7fa3', none: '#8b7c64'
};
const FLAG_LABEL = {
  cloudHide: '云阴不见', noEat: '当食不食', localUnseen: '本地不见',
  noEclipse: '全球无食', notAtStation: '长安不见', belowHorizon: '地平线下'
};

const DYNASTIES = [
  /* ---------------- 汉 ---------------- */
  {
    key: 'han',
    label: '汉',
    title: '《汉书·五行志》日食五十四条',
    subtitle: '古籍记载 ↔ 现代星历比对 · 长安见食判定',
    dataKey: 'han',
    renderer: 'unified',          // 详情渲染器：统一天文表格式（以宋版为范本）
    rangeMode: 'absolute',        // 时间轴用绝对 UTC（NASA 目录 TD 锚定，逐帧几何齐备）
    stationName: '观测地',
    initialRecord: null,
    /* 左侧列表显示格式（只影响展示，排序/检索/详情仍用原始字段）
       汉：编号补零 4 位；前 N 年 → -NNNN-MM-DD（负号表示公元前） */
    listId: id => String(id).padStart(4, '0'),
    listDate: label => {
      const m = /^(前|公元)?(\d{1,4})年(\d{1,2})月(\d{1,2})日$/.exec(String(label || ''));
      if (!m) return label;
      const y = (m[1] === '前' ? '-' : '') + m[2].padStart(4, '0');
      return `${y}-${m[3].padStart(2, '0')}-${m[4].padStart(2, '0')}`;
    },
    tabs: [
      { key: 'all', label: '全部' },
      { key: 'total', label: '全食' },
      { key: 'annular', label: '环食' },
      { key: 'partial', label: '偏食' },
      { key: 'none', label: '未对应' }
    ],
    chips: [
      { key: 'visible', label: '长安可见', test: r => r.visibility === 'visible' },
      { key: 'noEclipse', label: '全球无食', test: r => r.flags.includes('noEclipse') },
      { key: 'notAtStation', label: '长安不见', test: r => r.flags.includes('notAtStation') },
      { key: 'belowHorizon', label: '地平线下', test: r => r.flags.includes('belowHorizon') }
    ],
    searchFields: ['id', 'text', 'dateLabel', 'era', 'type'],
    methodology: {
      title: '判定分层 · 回原核查页',
      layers: [
        { n: '01', t: '原文层', c: '《汉书·五行志下之下》所载 54 条，年、月、干支、月相（朔 / 晦 / 先晦一日）、二十八宿宿度，逐字照录，不预设其误。' },
        { n: '02', t: '历日层', c: '按建寅、年中置闰回推太初历；月龄取 30 日与 1 日两种取值求解。西汉历谱月、日标准误差约为 0.31 月、0.97 日 —— 干支朔晦本身即带误差，不能当作精确钟点。' },
        { n: '03', t: '星历层', c: '几何由 pymeeus（ELP-2000/82 + VSOP87）+ 矢量影锥在 WGS84 椭球上复算，逐条以 NASA 五千年目录值（TD、ΔT、γ、食分、中心坐标）锚定并交叉校验；NASA 星历是今人对天球运动的计算重构，用作参照坐标系，不是古人的观测底本。' },
        { n: '04', t: '可见层', c: '以长安（34.3°N, 108.9°E）单独判定：扫描当日，取最大食分与当时太阳高度。「全球有食」与「长安见食」是两件事，必须分开写。' },
        { n: '05', t: '结论层', c: '未对应条目只记「窗口内无食 / 长安不可见 / 地平线下 / 历日传讹」，不给「伪造」结论；原文的真伪问题回到文献层处置，不由星历结果反推。原表旧中心/时刻字段经与 NASA 目录比对证实有系统误差，已由 NASA 值取代（详见条目「NASA 目录」行）。' }
      ],
      stats: [
        { b: '54', label: '汉书条目' },
        { b: '37', label: '长安见食' },
        { b: '17', label: '未对应 / 不可见' }
      ]
    },
    footnote: '几何由 pymeeus（ELP-2000/82 + VSOP87）+ 矢量影锥在 WGS84 椭球上复算，逐条以 NASA 五千年目录值（TD/ΔT/γ/食分/中心坐标）锚定并交叉校验；ΔT 用 NASA 逐条值（西汉段约 11000–13000 秒）。原表旧星历字段（中心坐标/时刻）有系统误差已弃用。2 条星历判全球无食者保留降级示意。'
  },

  /* ---------------- 晋 ---------------- */
  {
    key: 'jin',
    label: '晋',
    title: '两晋日食 · 六十条',
    subtitle: '《晋书·天文志》↔ 干支定日 · NASA 目录锚定 · 洛阳 / 建康 / 长安实况',
    dataKey: 'jin',
    renderer: 'unified',
    rangeMode: 'absolute',        // 逐帧几何齐备，时间轴用绝对 UTC（timeRange）
    stationName: '观测地',
    initialRecord: '0005',        // 泰始九年四月戊辰朔：洛阳全食（食分 0.92）示例
    listId: id => String(id).padStart(4, '0'),
    listDate: label => label,
    tabs: [
      { key: 'all', label: '全部' },
      { key: 'total', label: '全食' },
      { key: 'annular', label: '环食' },
      { key: 'partial', label: '偏食' },
      { key: 'none', label: '未对应' }
    ],
    chips: [
      { key: 'omen', label: '有占辞', test: r => !!r.extra && !!r.extra.omen },
      { key: 'jiji', label: '几既', test: r => !!r.extra && r.extra.tableText === '几既' },
      { key: 'hui', label: '晦日食', test: r => !!r.extra && r.extra.phase === '晦' },
      { key: 'noShuo', label: '不书朔', test: r => !!r.extra && r.extra.phase === '' },
      { key: 'noEclipse', label: '目录无食', test: r => r.flags.includes('noEclipse') },
      { key: '西晋', label: '西晋', test: r => r.dynastyLabel === '西晋' },
      { key: '东晋', label: '东晋', test: r => r.dynastyLabel === '东晋' }
    ],
    searchFields: ['id', 'era', 'lunarDate', 'source', 'text', 'extra.mansion'],
    methodology: {
      title: '史源与判定分层',
      layers: [
        { n: '01', t: '原文层', c: '《晋书·天文志》两晋日食 60 条（西晋 28 / 东晋 32），年号纪年、月序、干支、朔晦、宿度分野、占辞逐字照录；志文不书「朔」者（9 条）与晦日入食者（4 条）如实标注，不改写古籍用字。观测地按志文：西晋洛阳（建兴末蒙尘时记长安）、东晋建康。' },
        { n: '02', t: '历日层', c: '公历日由干支纪日独立定日（干支 60 日一循环，旧管线换算日 ±45 日窗口内取最近干支日，年序与年号年互检）：旧管线 21 条换算与干支纪日 ±1～6 日不合，已按干支重定。40 条经 NASA 五千年目录逐条锚定（含 2 条食甚跨午夜的地方日救援）；20 条目录该日无食——《晋书》两晋日食多系历官推步所记，如实降级标注「目录无食 · 存疑」并给近邻参考，不补食、不编几何。' },
        { n: '03', t: '历法层', c: '推步卡按《泰始历》（即魏《景初历》，杨伟造，景初元年 237 颁行；晋武帝泰始元年 265 改名行用至刘宋元嘉 444 年；岁实 673150/1843、朔实 134630/4559，十九年七闰）平朔近似推算历日与干支，与原文干支纪日自洽；农历月序为平朔近似参照列。' },
        { n: '04', t: '几何层', c: '几何由 pymeeus（ELP-2000/82 全项 + VSOP87，与 NASA 五千年谱同理论族）+ 矢量影锥在 WGS84 椭球上严格复算：中心线、本影带（中心线按局部半径加宽）、逐帧影心；ΔT 用 NASA 目录逐条值（两晋段约 6471–7916 秒）。复算与 NASA 值逐条校验：食分最大偏差 0.041、影心偏差中位 82 km、食甚时刻 ≤6 分钟。旧管线（erfa 后端）24 条判「不入食限」者经 NASA 目录逐条裁决，命中者给真实几何。' },
        { n: '05', t: '结论层', c: '按条目观测地（洛阳 / 建康 / 长安）单独判定可见性与太阳高度，「全球有食」与「本地见食」分开呈现；洛阳算 0.00 而志文有食者，恰证两晋记录多为推步而非实测，如实两存。宿度分野属星占占辞，仅照录不作解。' }
      ],
      stats: [
        { b: '60', label: '两晋条目' },
        { b: '40', label: '目录锚定' },
        { b: '20', label: '目录无食' },
        { b: '30', label: '有中心食带' }
      ]
    },
    footnote: '数据源：《晋书·天文志》两晋日食 60 条（西晋 28 / 东晋 32；底本中华书局点校本）。历日由干支纪日独立定日、经 NASA 五千年目录逐条锚定（含地方日跨午夜救援）；几何由 pymeeus + 矢量影锥复算，ΔT 用 NASA 逐条值；20 条目录无食者保留降级并标注存疑——晋书两晋日食多系历官推步所记，虚报与传讹如实两存。'
  },

  /* ---------------- 唐 ---------------- */
  {
    key: 'tang',
    label: '唐',
    title: '唐代日食 · 九十三条',
    subtitle: '《新唐书·天文志二》↔ 星历复算几何 · 长安 / 洛阳观测点实况',
    dataKey: 'tang',
    renderer: 'unified',          // 统一天文表格式；有逐帧几何者走宋式完整骨架
    rangeMode: 'absolute',        // 逐帧几何齐备，时间轴用绝对 UTC（timeRange）
    stationName: '观测地',
    initialRecord: '0002',        // 默认首条：可见环食示例（0001 长安不可见）
    /* 唐 dateLabel 已是 YYYY-MM-DD（4 位年），与宋版列宽对齐 */
    listId: id => String(id).padStart(4, '0'),
    listDate: label => label,
    tabs: [
      { key: 'all', label: '全部' },
      { key: 'total', label: '全食' },
      { key: 'annular', label: '环食' },
      { key: 'partial', label: '偏食' }
    ],
    chips: [
      { key: 'eaten', label: '食甚明载', test: r => !!r.extra && r.extra.tableText !== '日有食之' },
      { key: 'capital', label: '京师分', test: r => !!r.extra && r.extra.omen.includes('京师') },
      { key: 'omen', label: '有占辞', test: r => !!r.extra && !!r.extra.omen }
    ],
    searchFields: ['id', 'era', 'lunarDate', 'source', 'text', 'extra.mansion'],
    methodology: {
      title: '史源与判定分层',
      layers: [
        { n: '01', t: '原文层', c: '《新唐书·天文志二》（卷三十二）「日食」节凡九十三条，年号纪年、月份、干支、朔晦、宿度、占辞逐字照录，异文在条目脚注标注（如乾封二年「己丑／己酉」）。不改写古籍用字。' },
        { n: '02', t: '历日层', c: '公历日由「历朔干支星历匹配」精确确定：以精确朔时刻取长安地方时所在 civil 日，与原文朔（晦）日干支比对——87 条当日吻合；3 条食甚在 UT 16 时后、长安地方日跨午夜（目录按 UT 记日在前一日），按地方日吻合（#0036/#0039/#0089）；3 条该朔全球无食（NASA 目录判无），如实标注「历日存疑」保留降级示意。全部 90 条经 NASA 五千年目录独立旁证。' },
        { n: '03', t: '历法层', c: '推步卡按唐《大衍历》常数（通法 3040、岁分 1110343、朔实 89773）平朔近似推算历日与干支，与原文干支纪日自洽；农历月日、节气为近似，与原文分行呈现。' },
        { n: '04', t: '几何层', c: '几何由 pymeeus（ELP-2000/82 全项 + VSOP87，与 NASA 五千年谱同理论族）+ 矢量影锥在 WGS84 椭球上严格复算：中心线、本影带（中心线按局部半径加宽）、半影区（逐时刻轮廓并集包络）、逐帧影心；ΔT 用 NASA 目录逐条值（唐段约 2277–4538 秒）。复算与 NASA 值逐条校验：食分最大偏差 0.049、影心偏差中位 84 km、食甚时刻 ≤6 分钟。早期 pyephem 管线在唐代有约 0.3°（≈35 分钟）月球黄经系统偏差，已弃用重算。' },
        { n: '05', t: '结论层', c: '原文食型词与复算互证：上元二年「既」→ 长安复算 1.00、长安二年「几既」→ 0.96，自洽；至德元载「既」→ 长安复算不见食（安史乱中，所记或为历官推步或他地所见）、天宝十三载「几既」→ 0.84（长安近食带边缘，ΔT 摄动可改变可见性），矛盾如实标注，不作调解。宿度分野属星占占辞，仅照录。' }
      ],
      stats: [
        { b: '93', label: '天文志条目' },
        { b: '90', label: '星历有食' },
        { b: '3', label: '星历判无食' },
        { b: '79', label: '有中心食带' }
      ]
    },
    footnote: '数据源：《新唐书·天文志二》九十三条（原纲「凡唐著纪二百八十九年，日食九十三」）。公历日据历朔干支匹配、经 NASA 五千年目录逐条旁证（含 3 条长安地方日跨日吻合）；几何由 pymeeus + 矢量影锥复算，ΔT 用 NASA 逐条值；3 条 NASA 目录判无食者（#0044/#0088/#0090）保留降级示意并标注。'
  },
  /* ---------------- 宋 ---------------- */
  {
    key: 'song',
    label: '宋',
    isDefault: true,              // 默认首屏（宋有完整几何数据）
    title: '两宋日食 · 二百二十五条',
    subtitle: '古籍记载 ↔ 现代星历比对 · 开封 / 临安 / 开城三点记录',
    dataKey: 'song',
    renderer: 'unified',          // 详情渲染器：统一天文表格式（范本）
    rangeMode: 'absolute',        // 时间轴用绝对 UTC（timeRange）
    stationName: '观测地',
    initialRecord: '0001',        // 默认首条（建隆元年）；按 id 或 dateLabel 命中
    /* 左侧列表显示格式：宋的 dateLabel 已是 YYYY-MM-DD，仅将年份补足 4 位，
       与汉版列宽对齐（960-05-28 → 0960-05-28）；详情仍显示原始值。 */
    listId: id => String(id).padStart(4, '0'),
    listDate: label => {
      const m = /^(\d{1,4})-(\d{2})-(\d{2})$/.exec(String(label || ''));
      return m ? `${m[1].padStart(4, '0')}-${m[2]}-${m[3]}` : label;
    },
    tabs: [
      { key: 'all', label: '全部' },
      { key: 'total', label: '全食' },
      { key: 'annular', label: '环食' }
    ],
    chips: [
      { key: 'partial', label: '偏食', test: r => r.type === 'partial' && !(r.umbraPolygon && r.umbraPolygon.length) },
      { key: 'cloudHide', label: '云阴', test: r => r.flags.includes('cloudHide') },
      { key: 'noEat', label: '不食', test: r => r.flags.includes('noEat') },
      { key: 'localUnseen', label: '不见', test: r => r.visibility === 'unseen' && !r.flags.includes('noEclipse') },
      { key: 'dateOff', label: '历日存疑', test: r => !!(r.extra && r.extra.cat && r.extra.cat.dateOff) },
      { key: '北宋', label: '北宋', test: r => r.dynastyLabel === '北宋' },
      { key: '南宋', label: '南宋', test: r => r.dynastyLabel === '南宋' }
    ],
    searchFields: ['id', 'dateLabel', 'era', 'lunarDate', 'source', 'text'],
    methodology: {
      title: '史源与判定分层',
      layers: [
        { n: '01', t: '原文层', c: '225 条中 117 条有《宋史·天文志》等原记，年号纪年、月份、干支、朔晦逐字照录；另 108 条古籍无对应原记，依朔望回推补入并如实标注「无原记」，不编造。天文数值为复算结果，与原文分行呈现，不混为定论。' },
        { n: '02', t: '历日层', c: '117 条原记干支与中国公历日逐条自检；108 条补入条目的农历月序由原记朔日锚点链插值（历史月序本身权威，间距计数误差 <0.5 日；闰月按无中气置闰判定，锚点月序自检全链零不符），干支纪日由儒略日直推（精确）。224 条经 NASA 五千年目录逐条锚定旁证；食甚 UT 跨午夜者按观测地地方日（北宋开封 / 南宋临安）收编；旧管线 dateLabel 有 ±1 日系统误差的 6 条按目录日收编并标注「历日存疑」（干支自检佐证）；仅 #0058（原记「日當食不食」）目录 ±1 日内无可收编条目，保留降级。' },
        { n: '03', t: '历法层', c: '推步卡按宋《纪元历》（姚舜辅造，崇宁五年颁行；日法 7290、朔实 215278）平朔近似推算历日与干支，与原文干支纪日自洽；农历月日、节气为近似，与原文分行呈现。' },
        { n: '04', t: '几何层', c: '几何由 pymeeus（ELP-2000/82 全项 + VSOP87，与 NASA 五千年谱同理论族）+ 矢量影锥在 WGS84 椭球上严格复算：中心线、本影带（中心线按局部半径加宽）、半影区（逐时刻轮廓并集包络）、逐帧影心；ΔT 用 NASA 目录逐条值（宋段约 1800–2700 秒）。复算与 NASA 值逐条校验：食分偏差、影心偏差、食甚时刻偏差逐条给出。开封 / 临安 / 开城三点分别判定可见性与太阳高度，「全球有食」与「本地见食」分开呈现。' },
        { n: '05', t: '结论层', c: '古籍记「云阴不见」「当食不食」者照录原文、与复算互证，矛盾如实标注，不作调解；食型以 NASA 目录与复算为准，旧管线（单站驱动 + 旧星历层）的系统偏差已由 NASA 锚定值取代（详见条目「NASA 目录」行）。' }
      ],
      stats: [
        { b: '225', label: '两宋条目' },
        { b: '117', label: '有原记' },
        { b: '108', label: '朔望补入' },
        { b: '211', label: '有中心食带' }
      ]
    },
    footnote: '数据源：《宋史·天文志》等原记 117 条 + 依朔望回推补入 108 条（如实标注）。历日由干支自检与朔望回推、经 NASA 五千年目录逐条锚定旁证（食甚跨午夜按开封/临安地方日收编）；几何由 pymeeus + 矢量影锥复算，ΔT 用 NASA 逐条值；旧管线星历字段（单站驱动几何、经验 ΔT 插值）已弃用。时间体系：UTC 与地方视时并列，视时按当地经度折算。'
  },

];

/* 供外部读取（新朝代可在本数组继续追加） */
if (typeof window !== 'undefined') window.__DYNASTIES__ = DYNASTIES;

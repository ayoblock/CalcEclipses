/* =====================================================================
   历法推步模块 —— 各朝当期历法的历日推算（平朔平气近似）
   ---------------------------------------------------------------------
   依据（中国依据，正史律历志原文 + 中国学界主流整理）：
   · 太初历（汉，太初元年＝前104年颁行）：
       《汉书·律历志》载「日法八十一，月法二千三百九十二」，
       朔策 = 2392/81 日 ≈ 29.530864；十九年七闰（235 朔望月 = 19 回归年），
       岁实 = 235×朔策/19 = 562120/1539 日 ≈ 365.2502 日。
       历元「太初元年十一月甲子朔旦冬至」→ 儒略日 JDN 1683791（甲子日）。
   · 纪元历（北宋，姚舜辅造，崇宁五年＝1106年颁行）：
       《宋史·律历志》卷七十九：「日法七千二百九十，期实二百六十六万
       二千六百二十六，朔实二十一万五千二百七十八」。
       岁实 = 2662626/7290 ≈ 365.243621 日；朔策 = 215278/7290 ≈ 29.530590 日。
       本用定朔、平气、破章法；此处取崇宁五年冬至近距历元作平朔推步。
   · 大衍历（唐，一行造，开元十六年＝728年颁行，行用至唐末）：
       《新唐书·历志四上》：「通法三千四十，策实百一十一万三百四十三，
       揲法八万九千七百七十三」。通法即日法 3040；策实即岁分 1110343，
       岁实 = 1110343/3040 ≈ 365.243621 日；揲法即朔实 89773，
       朔策 = 89773/3040 ≈ 29.530592 日。
       原用定朔；此处取开元十二年（724）冬至近距历元作平朔近似推步。
       唐数据 dateLabel 由原文干支反推，与本历推步干支纪日自洽。
   · 泰始历（晋，即魏《景初历》，杨伟造，237 年颁行；晋泰始元年 265 改名，
       行用至刘宋元嘉二十一年 444）：
       《晋书·律历志下》：纪法 1843、周天 673150、通数 134630、日法 4559。
       岁实 = 673150/1843 ≈ 365.246881 日；朔策 = 134630/4559 ≈ 29.530599 日；
       十九年七闰。原用定朔；此处取泰始二年（266）冬至作平朔近似推步。

   精度边界（务必随结果一并呈现，不得隐去）：
   1. 干支纪日：精确。仅依赖连续儒略日，公式 idx=(JDN+49) mod 60，
      以 1949-10-01=甲子、2000-01-01=戊午 校验。
   2. 节气、农历月日、闰月：平朔平气近似。以平均朔策/岁实递推，
       未做太阳视运动不均匀（盈缩）与月球迟疾改正，也未用定朔定气。
       纪元历原用定朔，本模块为平朔近似，与实际历日可有 1 日上下出入。
   3. 数据集 dateLabel 为儒略历日（经 extra.jd 交叉核对确认），本模块据此换算 JDN。
   4. 历元双职责解耦：epochJDN = 真实冬至（气网格：节气/中气/月序）；
      shuoEpochJDN = 朔相位锚（以唐/宋史载朔日逐条实测校准，残差 ±1.5 日，
      系平朔 vs 定朔的正常范围）。宋「干支农历」月序由原记朔日锚点链插值
      （历史月序本身权威），推步卡月序为独立参照列，二者可有出入。
   5. 干支纪年：干支序号本身精确（(农历年-4) mod 60）；农历年归属以正月初一为界
      （现代夏历通行口径），界点由当期历常数平朔推得，前后约 1 日误差。
      汉代条目多为公元前，其时干支纪年尚未颁行（东汉元和二年＝85 年才通行），
      此处回标属「后世追纪」，界面须随结果标注。

   供 js/app.js 调用；新增朝代若需推步，在 CALENDARS 追加配置即可。
   ===================================================================== */
(function () {
  'use strict';

  var GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
  var ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
  var MONTH_CN = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'];
  var TERMS = ['冬至', '小寒', '大寒', '立春', '雨水', '惊蛰', '春分', '清明',
               '谷雨', '立夏', '小满', '芒种', '夏至', '小暑', '大暑', '立秋',
               '处暑', '白露', '秋分', '寒露', '霜降', '立冬', '小雪', '大雪'];

  /* 两历配置：sui=岁实(日)，shuo=朔策(日)，epochJDN=历元冬至儒略日 */
  var CALENDARS = {
    taichu: {
      key: 'taichu',
      name: '太初历',
      dynasty: '汉',
      sui: 562120 / 1539,
      shuo: 2392 / 81,
      epochJDN: 1683791,          // 前104年甲子朔旦冬至（儒略历）
      epochText: '太初元年（前104年）十一月甲子朔旦冬至',
      source: '《汉书·律历志》（月法2392、日法81，十九年七闰）',
      mean: true                  // 平朔，与太初历本术一致
    },
    jiyuan: {
      key: 'jiyuan',
      name: '纪元历',
      dynasty: '宋',
      sui: 2662626 / 7290,
      shuo: 215278 / 7290,
      /* 历元双职责解耦：epochJDN = 冬至锚（真实节气位置，供平气/月序）；
         shuoEpochJDN = 朔相位锚（以宋 117 条史载朔日实测校准：平朔网格早约
         4.9 日，历元后移 4.9 日）。校准后朔日锚点残差 ±1.5 日（平朔 vs
         定朔的正常范围），节气与月序网格不受影响。 */
      epochJDN: 2125366,          // 崇宁五年(1106)冬至（儒略历真实日期，气锚；儒略历节气漂移推算）
      shuoEpochJDN: 2125384.9,    // 朔相位（朔日锚点校准）
      epochText: '崇宁五年（1106年）冬至近距历元',
      source: '《宋史·律历志》卷七十九（期实2662626、朔实215278、日法7290）',
      mean: false                 // 原用定朔；本模块为平朔近似
    },
    taishi: {
      key: 'taishi',
      name: '泰始历',
      dynasty: '晋',
      /* 即魏《景初历》（杨伟造，237 颁行；晋泰始元年改名行用至刘宋 444 年）。
         《晋书·律历志下》：纪法 1843、周天 673150、通数 134630、日法 4559。
         岁实 = 673150/1843 ≈ 365.246881 日；朔策 = 134630/4559 ≈ 29.530599 日；
         十九年七闰（章岁 19 / 章月 235 / 章闰 7）。原用定朔；此处平朔近似。 */
      sui: 673150 / 1843,
      shuo: 134630 / 4559,
      /* 历元双职责解耦（同大衍/纪元历口径）：
         epochJDN = 冬至锚（真实节气位置，供平气/月序）；
         shuoEpochJDN = 朔相位锚（以两晋目录锚定的 38 条史载朔日实测校准，
         残差 -0.89..+0.35 日）。推步月序与志文月序一致率约 46%，
         系平朔 ±1.5 日残差在月界处的固有歧义（与唐/宋推步参照列同边界）。 */
      epochJDN: 1818569,          // 泰始二年(266)冬至（儒略历真实日期，气锚）
      shuoEpochJDN: 1820363.57,   // 朔相位（晋书朔日锚点校准）
    },
    dayan: {
      key: 'dayan',
      name: '大衍历',
      dynasty: '唐',
      sui: 1110343 / 3040,
      shuo: 89773 / 3040,
      /* 历元双职责解耦：epochJDN = 冬至锚（真实节气位置，供平气/月序）；
         shuoEpochJDN = 朔相位锚（以唐 91 条史载朔日实测校准：平朔网格晚约
         2.0 日，历元前移 2.0 日）。校准后朔日锚点残差 ±1.5 日（平朔 vs
         定朔的正常范围），节气与月序网格不受影响。 */
      epochJDN: 1985847,          // 开元十二年(724)冬至（儒略历真实日期，气锚；儒略历节气漂移推算）
      shuoEpochJDN: 1985853.0,    // 朔相位（朔日锚点校准）
      epochText: '开元十二年（724年）冬至近距历元',
      source: '《新唐书·历志四上》（通法3040、策实1110343、揲法89773）',
      mean: false                 // 原用定朔；本模块为平朔近似
    }
  };

  /* 朝代 key → 历法 key */
  var DYNASTY_CAL = { han: 'taichu', jin: 'taishi', song: 'jiyuan', tang: 'dayan' };

  /* 儒略历日期 → 儒略日数 JDN（整数，正午起算） */
  function jdnJulian(y, m, d) {
    var a = Math.floor((14 - m) / 12);
    var yy = y + 4800 - a;
    var mm = m + 12 * a - 3;
    return d + Math.floor((153 * mm + 2) / 5) + 365 * yy +
           Math.floor(yy / 4) - 32083;
  }

  /* 格里历日期 → JDN（仅用于锚点校验与 1582 年后日期） */
  function jdnGregorian(y, m, d) {
    var a = Math.floor((14 - m) / 12);
    var yy = y + 4800 - a;
    var mm = m + 12 * a - 3;
    return d + Math.floor((153 * mm + 2) / 5) + 365 * yy +
           Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) - 32045;
  }

  /* 解析 dateLabel 为儒略历 JDN（数据集 dateLabel 均为儒略历日）
     支持 "1149-04-09" / "前205年12月20日" / "公元2年11月23日" */
  function parseJDN(label) {
    if (!label) return null;
    label = String(label).trim();
    var m = /^(前|公元)?(\d+)年(\d{1,2})月(\d{1,2})日$/.exec(label);
    if (m) {
      var bc = m[1] === '前', y = parseInt(m[2], 10);
      // 天文年号：公元前 N 年 = -(N-1)，例 前205年 → -204
      var ay = bc ? -(y - 1) : y;
      return jdnJulian(ay, parseInt(m[3], 10), parseInt(m[4], 10));
    }
    m = /^(\d{3,4})-(\d{2})-(\d{2})$/.exec(label);
    if (m) return jdnJulian(parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10));
    return null;
  }

  /* 从 dateLabel 提取公历年份（天文年号：前N年 → -(N-1)） */
  function parseYear(label) {
    if (!label) return null;
    label = String(label).trim();
    var m = /^(前|公元)?(\d{1,4})年/.exec(label);
    if (m) {
      var y = parseInt(m[2], 10);
      return m[1] === '前' ? -(y - 1) : y;
    }
    m = /^(\d{1,4})-/.exec(label);
    return m ? parseInt(m[1], 10) : null;
  }

  /* 干支纪日（精确）：idx=(JDN+49) mod 60 */
  function ganzhiDay(jdn) {
    var i = ((jdn + 49) % 60 + 60) % 60;
    return { idx: i, text: GAN[i % 10] + ZHI[i % 12] };
  }

  /* 干支纪年（以农历正月初一为界，现代夏历通行口径）
     正月初一定位：上一回归年冬至所在朔 + 2 个朔策（冬至月=十一月，顺推两月即正月）。
     · 干支本身是 60 年循环，序号 (农历年 - 4) mod 60，精确；
     · 农历年归属依赖正月初一定位，此处用当期历常数平朔近似，界点前后约 1 日误差；
     · 数据集中汉代条目多为公元前，其时干支纪年尚未颁行（东汉元和二年 85 年才通行），
       此处按现代夏历口径回标，属「后世追纪」，界面须随结果标注。 */
  function ganzhiYear(jdn, cal, year) {
    if (jdn == null || !cal || year == null) return null;
    var S = cal.sui, M = cal.shuo, W = cal.epochJDN;
    var winterPrev = jdnJulian(year - 1, 12, 22);
    var y0 = Math.floor((winterPrev - W) / S);
    var winterY = W + y0 * S;
    var phase = ((winterY - W) % M + M) % M;
    var spring = winterY - phase + 2 * M;   // 正月初一 JDN
    var lunarYear = jdn >= spring ? year : year - 1;
    var i = ((lunarYear - 4) % 60 + 60) % 60;
    var yearText = lunarYear < 0 ? '前' + (1 - lunarYear) + '年' : lunarYear + '年';
    return {
      lunarYear: lunarYear,
      lunarYearText: yearText,
      text: GAN[i % 10] + ZHI[i % 12],
      beforeSpring: jdn < spring,
      boundaryNote: jdn >= spring
        ? '已在正月初一之后，属' + yearText + '（干支 ' + GAN[i % 10] + ZHI[i % 12] + '）'
        : '尚在正月初一之前，仍属' + yearText + '（干支 ' + GAN[i % 10] + ZHI[i % 12] + '）',
      nearBoundary: Math.abs(jdn - spring) <= 3
    };
  }

  /* 平朔平气推步。历元双职责解耦：
     · 气（节气/中气/月序）：epochJDN = 真实冬至位置；
     · 朔（朔日相位）：shuoEpochJDN = 经史载朔日锚点校准的相位基准。
     两网格独立，互不牵动。 */
  function pushuan(jdn, cal) {
    var S = cal.sui, M = cal.shuo, W = cal.epochJDN;
    var Ws = (typeof cal.shuoEpochJDN === 'number') ? cal.shuoEpochJDN : W;
    var years = (jdn - W) / S;
    var y0 = Math.floor(years);
    var winterY = W + y0 * S;               // 气：当前冬至（真实位置网格）

    // 平气：冬至后第 q 气（冬至=0，每气 S/24 日）
    var qi = (jdn - winterY) / (S / 24);
    var termIdx = Math.floor(qi) % 24;
    if (termIdx < 0) termIdx += 24;

    // 十一月朔（含冬至的朔）：朔相位取校准锚 Ws，与气锚 W 解耦
    var phase = ((winterY - Ws) % M + M) % M;
    var nov = winterY - phase;
    // 目标在第几个朔望月（朔相位网格残差 ±1.5 日，边界朔日的月归属存在
    // 固有歧义，按「包含月」处理；推步为独立参照列，与原记分行呈现）
    var idx = Math.floor((jdn - nov) / M);
    var lunarDay = Math.floor(jdn - (nov + idx * M)) + 1;
    // 月序：冬至月为十一月，顺推
    var monthOrder = ((11 + idx) % 12 + 12) % 12; // 0=正月
    // 无中气置闰判断（平气：一个朔望月内若无「中气」即闰月）
    // 中气为偶数序号（冬至0、大寒2…）；检查本月区内是否含中气
    var mStart = nov + idx * M, mEnd = mStart + M;
    var hasZhongqi = false;
    for (var k = Math.ceil((mStart - W) / (S / 24)); W + k * (S / 24) < mEnd; k++) {
      if (k % 2 === 0) { hasZhongqi = true; break; }
    }
    var leap = !hasZhongqi;
    // 闰月月序重复前月（闰三月紧跟三月，月序号仍为三）
    if (leap) { monthOrder -= 1; if (monthOrder < 0) monthOrder += 12; }

    return {
      lunarMonth: monthOrder,
      lunarMonthText: MONTH_CN[monthOrder] + '月',
      lunarDay: lunarDay,
      leap: leap,
      term: TERMS[termIdx],
      termExact: qi,
      ganzhi: ganzhiDay(jdn).text
    };
  }

  /* 对外主接口：compute(dateLabel, dynastyKeyOrCalKey) */
  function compute(dateLabel, key) {
    var jdn = parseJDN(dateLabel);
    if (jdn == null) return null;
    var calKey = CALENDARS[key] ? key : (DYNASTY_CAL[key] || null);
    if (!calKey) return null;
    var cal = CALENDARS[calKey];
    var r = pushuan(jdn, cal);
    var g = ganzhiDay(jdn);
    var gy = ganzhiYear(jdn, cal, parseYear(dateLabel));
    return {
      jdn: jdn,
      calendar: cal.name,
      calendarKey: calKey,
      dynasty: cal.dynasty,
      source: cal.source,
      epochText: cal.epochText,
      meanApprox: !cal.mean || true, // 无论平朔/定朔历，此处均为平气平朔近似
      ganzhiDay: g.text,
      ganzhiIdx: g.idx,
      ganzhiYear: gy ? gy.text : '—',
      ganzhiYearInfo: gy,
      term: r.term,
      lunarMonth: r.lunarMonthText + (r.leap ? '（闰）' : ''),
      lunarDay: r.lunarDay,
      lunarDateText: r.lunarMonthText + (r.leap ? '（闰）' : '') + (r.lunarDay === 1 ? '初一' : numberToCN(r.lunarDay)) + '日',
      note: cal.name + '推步（平朔平气近似）：' + ganZhiNote(cal) +
            ' 年干支按现代夏历「正月初一为界」回标，' +
            (cal.dynasty === '汉' ? '汉代属后世追纪；' : '') +
            '界点前后约1日误差。'
    };
  }

  function ganZhiNote(cal) {
    if (!cal.mean) return '原历用定朔，此处为平朔近似，历日可有1日出入；干支纪日精确。';
    return '平朔平气，与原历术一致；未计月球迟疾与太阳盈缩，历日可有1日出入；干支纪日精确。';
  }

  function numberToCN(n) {
    if (n <= 10) return ['初', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][n];
    if (n < 20) return '十' + ['', '一', '二', '三', '四', '五', '六', '七', '八', '九'][n - 10];
    var t = Math.floor(n / 10), o = n % 10;
    return ['', '二', '三'][t - 2] + '十' + (o ? ['', '一', '二', '三', '四', '五', '六', '七', '八', '九'][o] : '');
  }

  window.__CALENDAR__ = {
    compute: compute,
    parseJDN: parseJDN,
    parseYear: parseYear,
    ganzhiDay: ganzhiDay,
    ganzhiYear: ganzhiYear,
    jdnGregorian: jdnGregorian,
    jdnJulian: jdnJulian,
    calendars: CALENDARS,
    dynastyCal: DYNASTY_CAL
  };
})();

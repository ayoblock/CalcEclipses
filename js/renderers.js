/* =====================================================================
   详情渲染器 —— 由朝代配置的 renderer 字段选择
   新增朝代可复用现有渲染器，或在此追加自定义渲染器并在 registry 里按名引用。
   ===================================================================== */

function dms(v, pos, neg) {
  if (v === null || v === undefined || !isFinite(v)) return '—';
  return Math.abs(v).toFixed(1) + '°' + (v >= 0 ? pos : neg);
}

/* NASA 目录 UT → 观测地地方平时。经度偏移按朝代：汉/唐 = 长安 108.9°E（+7.26h），
   宋 = 北宋开封 114.3°E / 南宋临安 120.15°E。跨日只在文字里提示。 */
function catLocalTimeOff(cat, offSec) {
  if (!cat || !cat.ut) return '—';
  const m = /^(\d{2}):(\d{2}):(\d{2})$/.exec(cat.ut);
  if (!m) return '—';
  const s = (+m[1] * 3600 + +m[2] * 60 + +m[3] + (offSec || 26146)) % 86400;
  return ('0' + Math.floor(s / 3600)).slice(-2) + ':' + ('0' + Math.floor((s % 3600) / 60)).slice(-2);
}
/* 朝代 → NASA 目录地方时的观测地（名 + 经度偏移秒）
   汉/唐 = 长安 108.9°E（26146s）；晋 = 西晋洛阳 112.45°E / 东晋建康 118.79°E；
   宋 = 北宋开封 114.3°E / 南宋临安 120.15°E。 */
function catLocalSite(dk, rec) {
  if (dk === 'song')
    return (rec && rec.dynastyLabel === '南宋')
      ? { name: '临安', off: 28836 }
      : { name: '开封', off: 27432 };
  if (dk === 'jin')
    return (rec && rec.dynastyLabel === '东晋')
      ? { name: '建康', off: 28510 }
      : { name: '洛阳', off: 26988 };
  return { name: '长安', off: 26146 };
}
/* 详情文字中的观测地简称（判定行/说明行用；按条目站点回退） */
function dynSite(dk, rec) {
  if (dk === 'jin') {
    if (rec && rec.stations && rec.stations[0]) return rec.stations[0].name;
    return (rec && rec.dynastyLabel === '东晋') ? '建康' : '洛阳';
  }
  if (dk === 'song') return (rec && rec.dynastyLabel === '南宋') ? '临安' : '开封';
  return '长安';                                  // 汉 / 唐
}

/* 当期历法推步结果（平朔平气近似）；不可用或失败时安全降级 */
function calendarBlock(rec, dynastyKey) {
  var CAL = window.__CALENDAR__;
  if (!CAL) return '';
  var r = CAL.compute(rec.dateLabel, dynastyKey);
  if (!r) return '';
  return '<div class="cal-block">' +
    '<div class="cal-line"><span class="cal-name">' + r.calendar + '推步</span>' +
      '<span class="cal-date">' + r.lunarDateText + '</span>' +
      '<span class="cal-gz">年干支 ' + r.ganzhiYear + ' · 日干支 ' + r.ganzhiDay + '</span></div>' +
    '<div class="cal-meta">节气近' + r.term + ' · ' + r.source + '</div>' +
    '<div class="cal-note">' + r.note + '</div>' +
  '</div>';
}

/* ---------- 天文表格式（宋） ---------- */
function renderAstronomicalDetail(rec, cfg, util) {
  const stations = rec.stations || [];
  const visPts = stations.filter(p => p.visible);
  const cls = 't-' + (rec.type || 'none');
  const flags = [];
  if (rec.flags.includes('noEat')) flags.push('<span class="flag mute">【当食不食】</span>');
  if (rec.flags.includes('cloudHide')) flags.push('<span class="flag">【云阴不见】</span>');
  if (visPts.length === 0 && !rec.flags.includes('cloudHide') && !rec.flags.includes('noEat'))
    flags.push('<span class="flag warn">【文献与天文回推存在矛盾】</span>');

  const ptLine = stations.map(p => `${p.name} ${p.visible ? '食分 ' + (p.obsc || 0).toFixed(2) : '地平线下'}（${dms(p.lat, 'N', 'S')}, ${dms(p.lon, 'E', 'W')}）`).join('；');

  const center = rec.center || {};
  return `
    <div class="entry-head">
      <span class="no num">第 ${rec.id} 条</span>
      <span class="type ${cls}">${TYPE_LABEL[rec.type] || rec.type || '—'}</span>
      <span class="era">${rec.era || ''}</span>
    </div>
    ${flags.length ? `<div class="flag-row">${flags.join('')}</div>` : ''}
    <blockquote class="quote">${(rec.text || '（原文待录入）')}</blockquote>

    <div class="kv">
      <div class="k">出处</div><div class="v">${rec.source || '—'}</div>
      <div class="k">观测地</div><div class="v">${rec.dynastyLabel || '—'}·${stations.map(p => p.name).join('、') || '—'}</div>
      <div class="k">干支农历</div><div class="v">${rec.lunarDate || '—'}</div>
      <div class="k">换算日期</div><div class="v"><span class="hi num">${rec.dateLabel}</span> <span class="dim">（中国公历）</span></div>
      <div class="k">本地复算</div><div class="v">${stations.map(p => `<div class="pt-line">${p.name}
        <span class="num">${p.visible ? '食分 ' + (p.obsc || 0).toFixed(2) + ' · 太阳高 ' + p.alt + '°' : (p.visible === false ? '地平线下 · 不可见' : '目录无食 · 未复算')}</span>
        ${p.distKm != null ? `<span class="dim">距中心 ${p.distKm} km</span>` : ''}</div>`).join('') || '—'}</div>
    </div>
    ${calendarBlock(rec, 'song')}
    <div class="sep"></div>
    <div class="kv">
      <div class="k">NASA 编号</div><div class="v">${rec.extra && rec.extra.nasaId ? '<span class="num">' + rec.extra.nasaId + '</span>' : '<span class="dim">待匹配</span>'}
        <span class="dim">· ${TYPE_LABEL[rec.type] || ''} · 影带宽 ${(rec.pathWidthKm || 0).toFixed(0)} km</span></div>
      <div class="k">食甚时刻</div><div class="v">${rec.timeRange && rec.timeRange.maxEclipse ? util.fmtDateTime(rec.timeRange.maxEclipse) : '—'}</div>
      <div class="k">食甚中心</div><div class="v"><span class="num">${dms(center.lat, 'N', 'S')} ${dms(center.lon, 'E', 'W')}</span>
        <span class="dim">太阳高度 ${center.alt != null ? center.alt : '—'}°</span></div>
      <div class="k">最大食分</div><div class="v"><span class="num">${(rec.maxMagnitude || 0).toFixed(2)}</span>
        <span class="dim">· 中心见食 ${rec.durationSec || 0} 秒</span></div>
      <div class="k">本影半径</div><div class="v"><span class="num">${(rec.umbraRadiusKm || 0).toFixed(0)} km</span>
        <span class="dim">· 半影张角 ${(rec.penumbraRadiusDeg || 0).toFixed(1)}°</span></div>
      <div class="k">中心线</div><div class="v"><span class="num">${(rec.centralLine || []).length}</span> 个采样点
        <span class="dim">（食甚 ±2.5 小时）</span></div>
    </div>

    <div class="note">
      <b>${cfg.methodology ? cfg.methodology.title : '说明'}</b>
      ${rec.shadowFrames && rec.shadowFrames.length
        ? '以食甚前后 ±2.5 小时、每 4 分钟取一次月影在地球上的落区：半影张角 ' + (rec.penumbraRadiusDeg || 0).toFixed(1) + '°，斜射时落区是椭圆而非常规圆。叠起来扫过的带即半影区，深色为本影（环食为伪本影），白线为食带中心线。'
        : '本条只有食甚中心与观测点食分等标量，无影带几何，三维区以点位降级显示。'}
    </div>

    <div class="foot-note">
      ${rec.extra && rec.extra.remark ? '<div>' + rec.extra.remark + '</div>' : ''}
      ${cfg.footnote ? '<div class="warn">' + cfg.footnote + '</div>' : ''}
    </div>`;
}

/* ---------- 考据叙述式（汉） ---------- */
function renderNarrativeDetail(rec, cfg, util) {
  const e = rec.extra || {};
  const sub = e.sub || rec.visibility;
  const mag = (e.mag || 0), alt = (e.alt || 0);
  let judge, judgeNote;
  if (sub === 'visible') {
    judge = `<span class="ok">长安可见 · 食分 ${mag.toFixed(2)} · 太阳高度 ${alt}°</span>`;
    judgeNote = e.paper_mag != null ? `论文表列：${e.paper_mag}；本页重算 ${mag.toFixed(2)}，同量级` : '本页星历重算';
  } else if (sub === 'below') {
    judge = `<span class="no">长安不可见 · 食甚太阳高度 ${e.alt_ecl}°（地平线下）</span>`;
    judgeNote = '日未出或已入，天光不在此处';
  } else if (sub === 'nolat') {
    judge = `<span class="no">长安无食 · 半影未及关中</span>`;
    judgeNote = '全球有食，长安不在可见带内';
  } else {
    judge = `<span class="no">长安无食（该日全球无食）</span>`;
    judgeNote = '论文判定：' + (e.paper || '无食');
  }

  let nearRow;
  if (e.near) {
    const nt = TYPE_LABEL[e.near.total ? (e.near.mag >= 0.9 ? 'total' : 'annular') : 'partial'];
    nearRow = `${nt}（${e.near.off > 0 ? '+' : ''}${e.near.off} 日）
        <span class="note">${e.near.date} · 长安食分 ${(e.near.mag || 0).toFixed(2)} · 太阳高度 ${e.near.alt}°</span>`;
  } else {
    nearRow = `本场即窗口内最近一场（${e.off > 0 ? '+' : ''}${e.off} 日）
        <span class="note">${e.instant} 食甚 · 影心 ${dms(rec.center.lat, 'N', 'S')} ${dms(rec.center.lon, 'E', 'W')}</span>`;
  }
  const nasa = e.near
    ? `未对应 <span class="note">±3 日窗口内无全球日食条目</span>`
    : `命中 · JD ${e.jd} <span class="note">相距 ${e.off} 日 · 日月经纬分离 ${(e.gsep || 0).toFixed(2)}°</span>`;

  let explain;
  if (sub === 'visible') {
    explain = `原表日期与这场日食相距 <b>${e.off}</b> 日，落在 ±3 日窗口内 —— 这一条对得上。全球食甚 ${e.instant}（北京时间），月影中心在 ${dms(rec.center.lat, 'N', 'S')} ${dms(rec.center.lon, 'E', 'W')}，长安食分 <b>${mag.toFixed(2)}</b>、食甚太阳高度 <b>${alt}°</b>。`;
  } else if (sub === 'nolat') {
    explain = `窗口内确有全球日食（相距 ${e.off} 日，食甚 ${e.instant}），但长安食分为 <b>0</b> —— 月球半影锥没有扫过关中。不是这天没有食，是这一天长安看不见。`;
  } else if (sub === 'below') {
    explain = `全球日食确在窗口内（相距 ${e.off} 日，食甚 ${e.instant}），但食甚时长安太阳高度 <b>${e.alt_ecl}°</b> —— 太阳在地平线下，日未出或已入。属于「日出前 / 日没后」一类：食在天上，长安不可见。`;
  } else {
    const n = e.near || {};
    explain = `原表日期 ±3 日窗口内<b>没有任何全球日食条目</b> —— 不是「看不见」，是这天没有食可看。最近的一场在 <b>${n.off} 日</b>。那一场长安食分 ${(n.mag || 0).toFixed(2)}、太阳高度 ${n.alt}° —— 若记录历日差了一个朔望月，这条就说得通；否则就是原文或传抄的问题。`;
  }

  return `
  <div class="d-head">
    <div>
      <div class="d-id">第 ${rec.id} 条 / 共 54</div>
      <div class="d-title">${TYPE_LABEL[rec.type] || rec.type}<span class="tag ${rec.type}">${sub === 'noecl' ? '全球无食' : sub === 'nolat' ? '长安不见' : sub === 'below' ? '地平线下' : '窗口命中'}</span></div>
      <div class="d-era">${rec.era} · 西汉</div>
    </div>
  </div>
  <div class="sect">
    <h5>古籍原文</h5>
    <div class="quote">${rec.text}<span class="src">${rec.source}</span></div>
  </div>
  <div class="sect">
    <h5>比对与判定</h5>
    <table class="kv">
      <colgroup><col class="c1"><col></colgroup>
      <tr><td class="k">换算日期</td><td class="v">${rec.dateLabel}（中国公历）<span class="note">积日 ${e.jd} · 食甚 ${e.instant}（北京时间）</span></td></tr>
      <tr><td class="k">当期历推步</td><td class="v">${(function () {
        var C = window.__CALENDAR__, r = C && C.compute(rec.dateLabel, 'han');
        return r ? (r.calendar + '　' + r.lunarDateText + '　年干支 ' + r.ganzhiYear + ' · 日干支 ' + r.ganzhiDay +
          '<span class="note">节气近' + r.term + ' · ' + r.note + '</span>') : '—';
      })()}</td></tr>
      <tr><td class="k">NASA 比对</td><td class="v">${nasa}</td></tr>
      <tr><td class="k">长安可见</td><td class="v">${judge}<span class="note">${judgeNote}</span></td></tr>
      <tr><td class="k">月影中心</td><td class="v">${dms(rec.center.lat, 'N', 'S')} ${dms(rec.center.lon, 'E', 'W')}<span class="note">食甚时太阳直射点，月影以此为中心</span></td></tr>
      <tr><td class="k">近邻候选</td><td class="v">${nearRow}</td></tr>
    </table>
  </div>
  <div class="sect">
    <h5>说明</h5>
    <div class="explain">${explain}</div>
    <div class="memo">
      <strong>三类「看不见」</strong>：全球无食（窗口内本无食可看）／全球有食而长安不可见（半影未及或日在地平线下）／历日传讹（干支、月相与历谱不合）。<br>
      <strong>未对应 ≠ 伪造</strong>，也不等于「天象已证伪」；它只说明这一条落在现代星历的窗口之外，需回到原文与历谱分层处置。
    </div>
  </div>
  <div class="d-link" id="openSheet">回原核查页 <span>看原文与判定分层 →</span></div>`;
}

/* ---------- 统一详情渲染器（以宋版天文表格式为范本） ----------
   结构骨架完全沿用 renderAstronomicalDetail：
     条目头 → 旗标 → 原文 → 文献/历日 kv → 历法推步卡 → 分隔 →
     天文复算 kv → 说明 note → 脚注 foot-note。
   汉数据缺几何字段（中心线/影带/逐帧），但 extra 里有食分、高度、
   积日、近邻候选等标量，映射到范本的对应槽位；几何槽位显示降级说明。
   同时把汉独有的考据判定（长安可见判定、近邻候选、三类看不见）
   融入范本的 kv 与 note 中，避免信息丢失。
   ------------------------------------------------------------------ */
function renderUnifiedDetail(rec, cfg, util) {
  const stations = rec.stations || [];
  const e = rec.extra || {};
  const center = rec.center || {};
  const dk = /* 朝代 key：优先取配置，回退按 stationName 判定 */ (cfg.key || (cfg.dataKey));
  const isHan = dk === 'han';
  /* 降级判定完全由数据驱动：无逐帧几何且无 NASA 锚定 timeRange 者走降级骨架。
     汉 noecl、唐/宋 NASA 目录判无食条目同走此路径（宋旧管线 dateLabel ±1 日
     且目录该日无食、经 ±1 日救援仍无食者极少，落入此处）。 */
  const hasGeom = !!(rec.shadowFrames && rec.shadowFrames.length) ||
                  !!(rec.timeRange && rec.timeRange.start);
  const hanDegraded = isHan && !hasGeom;
  const isDegraded = !isHan && !hasGeom;
  const dynastyName = cfg.label || (isHan ? '汉' : isDegraded ? '唐' : '');
  const cls = 't-' + (rec.type || 'none');

  /* --- 换算日期：汉的 dateLabel 是「前205年12月20日」，附中国公历说明 --- */
  const dateCell = `<span class="hi num">${rec.dateLabel}</span> <span class="dim">（中国公历）</span>`;

  /* --- 本地复算：宋用 stations[].obsc/alt/distKm；汉 station 同结构。
         visible=null（晋目录无食降级条目）→「目录无食 · 未复算」。 --- */
  const ptLine = stations.map(p => `<div class="pt-line">${p.name}
      <span class="num">${p.visible ? '食分 ' + (p.obsc || 0).toFixed(2) + ' · 太阳高 ' + p.alt + '°' : (p.visible === false ? '地平线下 · 不可见' : '目录无食 · 未复算')}</span>
      ${p.distKm != null ? `<span class="dim">距中心 ${p.distKm} km</span>` : ''}</div>`).join('') || '—';

  /* --- 第一组 kv（文献与历日）：范本槽位。朝代并入观测地行（如「西汉·长安」）
         干支纪日行已删：推步卡（calendarBlock）已含日干支，不重复显示 --- */
  const siteNames = stations.map(p => p.name).join('、') || '—';
  const siteLabel = `${rec.dynastyLabel || '—'}·${siteNames}`;
  const kvTop = `
      <div class="k">出处</div><div class="v">${rec.source || '—'}</div>
      <div class="k">观测地</div><div class="v">${siteLabel}</div>
      <div class="k">干支农历</div><div class="v">${rec.lunarDate || '—'}</div>
      <div class="k">换算日期</div><div class="v">${dateCell}</div>
      <div class="k">本地复算</div><div class="v">${ptLine}</div>`;

  /* --- 第二组 kv（天文复算）：几何字段降级为说明 --- */
  let kvAstro, noteText;
  if (hanDegraded || isDegraded) {
    /* 汉 / 唐 / 晋（降级数据）：extra 标量 → 范本槽位。
       唐无星历比对字段（instant/off/gsep/near），按考据式标注，不编造。 */
    const site = dynSite(dk, rec);
    const sub = e.sub || rec.visibility;
    const realCalc = e.dateMethod && e.dateMethod.includes('星历');   // 唐：已星历复算
    let judge;
    if (sub === 'visible')       judge = `<span class="ok">${site}可见 · 食分 ${(e.mag || 0).toFixed(2)} · 太阳高度 ${e.alt}°</span>`;
    else if (sub === 'below')    judge = `<span class="no">${site}不可见 · 食甚太阳高度 ${e.alt_ecl}°（地平线下）</span>`;
    else if (sub === 'nolat')    judge = `<span class="no">${site}无食 · 半影未及</span>`;
    else if (sub === 'unseen' || sub === 'none')
      judge = (rec.maxMagnitude && rec.maxMagnitude > 0)
        ? `<span class="no">${site}无食 · 半影未及或在地平线下（全球有食）</span>`
        : `<span class="no">${site}无食（该日全球无食）</span>`;
    else                          judge = `<span class="no">${site}无食（该日全球无食）</span>`;

    let nearRow;
    if (e.catNone && e.catNear && e.catNear.length) {
      /* 唐：NASA 目录判该日无食（原文纪日存疑），列近邻参考 */
      nearRow = e.catNear.map(nn => {
        const nt = TYPE_LABEL[nn.type === 'T' ? 'total' : nn.type === 'A' ? 'annular' : 'partial'];
        return `${nt}（${nn.off > 0 ? '+' : ''}${nn.off} 日）<span class="note">${nn.date} · 全球食分 ${nn.mag.toFixed(2)}</span>`;
      }).join('；');
    } else if (e.near) {
      const nt = TYPE_LABEL[e.near.total ? (e.near.mag >= 0.9 ? 'total' : 'annular') : 'partial'];
      nearRow = `${nt}（${e.near.off > 0 ? '+' : ''}${e.near.off} 日）<span class="note">${e.near.date} · ${site}食分 ${(e.near.mag || 0).toFixed(2)} · 高度 ${e.near.alt}°</span>`;
    } else {
      nearRow = `本场即窗口内最近一场（${e.off > 0 ? '+' : ''}${e.off} 日）`;
    }
    const nasa = isHan
      ? (e.near
          ? `未对应 <span class="dim">±3 日窗口内无全球日食；${nearRow}</span>`
          : `命中 · JD ${e.jd} <span class="dim">相距 ${e.off} 日 · 经纬分离 ${(e.gsep || 0).toFixed(2)}°</span>`)
      : e.catNone
        ? `NASA 目录判无食 <span class="dim">${e.catNone}</span>`
        : realCalc
          ? `星历复算 <span class="dim">${e.match || ''} · 积日 JD ${e.jdn || e.jd || '—'}</span>`
          : `未作现代星历复算 <span class="dim">据原文干支回推公历日 · 积日 JD ${e.jdn || e.jd || '—'}</span>`;
    const centerLine = isHan
      ? `<div class="k">近邻候选</div><div class="v">${nearRow}</div>`
      : ((dk === 'tang' || dk === 'jin') && e.catNear)
        ? `<div class="k">近邻候选</div><div class="v">${nearRow}</div>`
        : `<div class="k">宿度 / 分野</div><div class="v"><span class="num">${e.mansion || '—'}</span>${e.omen ? ` <span class="dim">${e.omen}</span>` : ''}</div>`;

    const judgeLabel = isHan ? `${site}判定` : (realCalc ? `${site}判定` : '示意值');
    const geomRow = (rec.penumbraPolygon && rec.penumbraPolygon.length)
      ? `<span class="dim">半影区已由矢量影锥逐时刻复算（并集包络）；本条无中心食（本影未触地），故无中心线／本影带</span>`
      : `<span class="dim">${dynastyName}数据无中心线 / 本影 / 逐帧几何，三维区按影心与食分示意渲染${e.magIsDemo ? '；食分、高度为示意非实测' : ''}</span>`;

    kvAstro = `
      <div class="k">星历比对</div><div class="v">${nasa}</div>
      <div class="k">食甚时刻</div><div class="v">${e.instant || '—'} <span class="dim">${isHan ? '（北京时间）· ' : ''}积日 JD ${e.jd || e.jdn || '—'}</span></div>
      <div class="k">食甚中心</div><div class="v"><span class="num">${dms(center.lat, 'N', 'S')} ${dms(center.lon, 'E', 'W')}</span>
        <span class="dim">太阳高度 ${e.alt != null ? e.alt : '—'}°${e.centerIsDemo ? ' · 观测地示意' : ''}</span></div>
      <div class="k">最大食分</div><div class="v"><span class="num">${(e.mag || 0).toFixed(2)}</span>
        <span class="dim">${judgeLabel}：${judge}</span></div>
      <div class="k">影带几何</div><div class="v">${geomRow}</div>
      ${centerLine}`;

    noteText = isHan
      ? `以长安（34.3°N, 108.9°E）单独判定：${judge}。全球有食与长安见食分开写；未对应只记「窗口内无食 / 长安不可见 / 地平线下 / 历日传讹」，不给伪造结论。`
      : (dk === 'song' || dk === 'jin')
        ? `本条 NASA 五千年目录该日（中国公历）无日食，±1 日内亦无可收编条目；《晋书·天文志》两晋日食多系历官推步所记，目录无食者或为推步虚报、或为月序/干支传讹，如实标注存疑，三维区为示意渲染，不作定论。`
        : `本条据《新唐书·天文志二》原文「${e.tableText || '日有食之'}」照录。${e.match || ''}${e.dateMethod ? '（' + e.dateMethod + '）' : ''}；本条无逐帧几何，三维区为示意渲染，不作定论。`;
  } else {
    /* 宋 / 唐 / 汉（有几何）：沿用范本的第二组 kv 与说明 */
    const eCat = e.cat || null;
    const localSite = catLocalSite(dk, rec);
    const catVal = eCat
      ? `命中 · 目录 ${eCat.catNum} 号 <span class="dim">NASA TD ${eCat.td}${eCat.ut ? ' · UT ' + eCat.ut : ''} · ΔT ${eCat.dt}s · γ ${eCat.gamma} · NASA 食分 ${eCat.mag}${eCat.saros ? ' · Saros ' + eCat.saros : ''}${eCat.dur ? ' · 中心食 ' + eCat.dur : ''}</span>` +
        ((eCat.lat != null) ? `<div class="k">食甚轴点</div><div class="v"><span class="num">${dms(eCat.lat, 'N', 'S')} ${dms(eCat.lon, 'E', 'W')}</span><span class="dim">（NASA greatest eclipse）· ${localSite.name}地方时约 ${catLocalTimeOff(eCat, localSite.off)}</span></div>` : '') +
        (eCat.dateOff ? `<span class="dim">· 原纪日与目录日相差 1 日（历日存疑，几何按目录日 ${eCat.catDate || ''} 复算）</span>` : '')
      : (rec.extra && rec.extra.nasaId)
        ? '<span class="num">' + rec.extra.nasaId + '</span>'
        : (dk === 'tang' ? '<span class="dim">未配 · 本引擎自算</span>' : '<span class="dim">待匹配</span>');
    const nasaLabel = eCat ? 'NASA 目录' : 'NASA 编号';
    kvAstro = `
      <div class="k">${nasaLabel}</div><div class="v">${catVal}
        <span class="dim">· ${TYPE_LABEL[rec.type] || ''}${rec.pathWidthKm ? ' · 影带宽 ' + rec.pathWidthKm.toFixed(0) + ' km' : ''}</span></div>
      <div class="k">食甚时刻</div><div class="v">${rec.timeRange && rec.timeRange.maxEclipse ? util.fmtDateTime(rec.timeRange.maxEclipse) : '—'}</div>
      <div class="k">食甚中心</div><div class="v"><span class="num">${dms(center.lat, 'N', 'S')} ${dms(center.lon, 'E', 'W')}</span>
        <span class="dim">太阳高度 ${center.alt != null ? center.alt : '—'}°</span></div>
      <div class="k">最大食分</div><div class="v"><span class="num">${(rec.maxMagnitude || 0).toFixed(2)}</span>
        <span class="dim">· 中心见食 ${rec.durationSec || 0} 秒</span></div>
      ${rec.umbraRadiusKm ? `<div class="k">本影半径</div><div class="v"><span class="num">${(rec.umbraRadiusKm || 0).toFixed(0)} km</span>
        <span class="dim">· 半影张角 ${(rec.penumbraRadiusDeg || 0).toFixed(1)}°</span></div>` : ''}
      <div class="k">中心线</div><div class="v"><span class="num">${(rec.centralLine || []).length}</span> 个采样点
        <span class="dim">（食甚 ±2.5 小时）</span></div>
      ${((dk === 'tang' || dk === 'jin') && (e.mansion || e.omen)) ? `<div class="k">宿度 / 分野</div><div class="v"><span class="num">${e.mansion || '—'}</span>${e.omen ? ` <span class="dim">${e.omen}</span>` : ''}</div>` : ''}`;
    noteText = rec.shadowFrames && rec.shadowFrames.length
      ? '以食甚前后 ±2.5 小时、每 4 分钟取一次月影在地球上的落区：半影张角 ' + (rec.penumbraRadiusDeg || 0).toFixed(1) + '°，斜射时落区是椭圆而非常规圆。深色带为本影（环食为伪本影）全程扫掠带，白线为食带中心线，动态圆为当前时刻的月影（外圈半影、内圈本影）；半影全程落区因跨数千公里、叠加后呈大片暗斑，已不再静态渲染。'
      : '本条只有食甚中心与观测点食分等标量，无影带几何，三维区以点位降级显示。';
  }

  /* --- 旗标：范本样式 --- */
  const flags = [];
  /* 唐 / 晋：原文食型词作旗标（有几何/降级皆显示），忠实反映古籍用字 */
  if (dk === 'tang' || dk === 'jin') {
    if (e.tableText === '既') flags.push('<span class="flag">【既·全食】</span>');
    else if (e.tableText === '几既') flags.push('<span class="flag">【几既·近全】</span>');
    else if (e.tableText === '不尽如钩') flags.push('<span class="flag">【不尽如钩】</span>');
    else if (e.tableText && e.tableText !== '日有食之') flags.push(`<span class="flag">【${e.tableText}】</span>`);
    if (e.match && e.match.includes('重配未果')) flags.push('<span class="flag warn">【星历判无食 · 历日存疑】</span>');
    else if (e.match && e.match.includes('远窗')) flags.push('<span class="flag warn">【远窗重配 · 原纪月存疑】</span>');
  }
  if ((dk === 'song' || dk === 'jin') && isDegraded) flags.push('<span class="flag warn">【历日存疑 · 目录无食】</span>');
  if (!isHan && !isDegraded) {
    if (rec.flags.includes('noEat')) flags.push('<span class="flag mute">【当食不食】</span>');
    if (rec.flags.includes('cloudHide')) flags.push('<span class="flag">【云阴不见】</span>');
    if (dk === 'song' && e.cat && e.cat.dateOff) flags.push('<span class="flag warn">【历日差一日 · 存疑】</span>');
    const visPts = stations.filter(p => p.visible);
    if (visPts.length === 0 && !rec.flags.includes('cloudHide') && !rec.flags.includes('noEat') && !(dk === 'tang' && rec.type === 'none') && !(dk === 'song' && rec.flags.includes('noEclipse')))
      flags.push('<span class="flag warn">【文献与天文回推存在矛盾】</span>');
  } else if (isHan) {
    const sub = e.sub || rec.visibility;
    if (sub === 'noecl') flags.push('<span class="flag mute">【全球无食】</span>');
    else if (sub === 'nolat') flags.push('<span class="flag warn">【长安不见】</span>');
    else if (sub === 'below') flags.push('<span class="flag warn">【地平线下】</span>');
  }

  return `
    <div class="entry-head">
      <span class="no num">第 ${rec.id} 条</span>
      <span class="type ${cls}">${TYPE_LABEL[rec.type] || rec.type || '—'}</span>
      <span class="era">${rec.era || ''}</span>
    </div>
    ${flags.length ? `<div class="flag-row">${flags.join('')}</div>` : ''}
    <blockquote class="quote">${(rec.text || '（原文待录入）')}</blockquote>

    <div class="kv">${kvTop}</div>
    ${calendarBlock(rec, dk)}
    <div class="sep"></div>
    <div class="kv">${kvAstro}</div>

    <div class="note">
      <b>${cfg.methodology ? cfg.methodology.title : '说明'}</b>
      ${noteText}
    </div>

    <div class="foot-note">
      ${isHan ? '<div>三类「看不见」：全球无食／全球有食而长安不可见／历日传讹；未对应 ≠ 伪造，需回到原文与历谱分层处置。</div>' : ''}
      ${isDegraded && !isHan && e.variant ? '<div>校勘：' + e.variant + '</div>' : ''}
      ${rec.extra && rec.extra.remark ? '<div>' + rec.extra.remark + '</div>' : ''}
      ${cfg.footnote ? '<div class="warn">' + cfg.footnote + '</div>' : ''}
    </div>
    <div class="d-link" id="openSheet">回原核查页 <span>看原文与判定分层 →</span></div>`;
}

/* ---------- 渲染器注册表 ---------- */
const RENDERERS = {
  astronomical: renderAstronomicalDetail,
  narrative: renderNarrativeDetail,
  unified: renderUnifiedDetail
};

/* ---------- 方法论弹窗内容 ---------- */
function renderMethodology(cfg) {
  const m = cfg.methodology;
  if (!m) return '';
  const layers = (m.layers || []).map(l =>
    `<div class="layer"><div class="n">${l.n}</div><div class="t">${l.t}</div><div class="c">${l.c}</div></div>`).join('');
  const stats = m.stats
    ? `<div class="cnt">${m.stats.map(s => `<div><b>${s.b}</b><span>${s.label}</span></div>`).join('')}</div>`
    : '';
  return layers + stats;
}

if (typeof window !== 'undefined') {
  window.__renderers__ = RENDERERS;
  window.__renderMethodology__ = renderMethodology;
}

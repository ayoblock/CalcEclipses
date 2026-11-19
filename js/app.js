/* =====================================================================
   统一应用核心：Cesium 引擎 + 朝代切换 + 统一筛选/列表/详情/时间轴
   数据来自 window.__ECLIPSE_DATA__，朝代配置来自 window.__DYNASTIES__。
   ===================================================================== */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const pad2 = n => String(n).padStart(2, '0');
  const RENDERERS = window.__renderers__;
  const renderMethodology = window.__renderMethodology__;

  /* ---------- 工具 ---------- */
  /* BC 年份 ISO（-00204-12-20T…Z，儒略历口径）Cesium 不支持：
     用儒略历 JDN 直构 JulianDate（与数据生成端 iso_utc 同口径）。
     正年份仍走 Cesium.fromIso8601。结果按 ISO 串缓存（逐帧回调频繁取用）。 */
  const _isoJD = new Map();
  function J(iso) {
    if (typeof iso !== 'string') return iso;
    let v = _isoJD.get(iso);
    if (v !== undefined) return v;
    if (iso[0] === '-') {
      const m = /^-(\d{6})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$/.exec(iso);
      if (!m) { _isoJD.set(iso, null); return null; }
      const y = -parseInt(m[1], 10), mo = +m[2], d = +m[3];
      // 儒略历 JDN（与 tools/build_tang_geom.jdn_julian 同式；负年 floor 除法一致）
      const a = Math.floor((14 - mo) / 12), yy = y + 4800 - a, mm = mo + 12 * a - 3;
      const jdn = d + Math.floor((153 * mm + 2) / 5) + 365 * yy + Math.floor(yy / 4) - 32083;
      const secs = +m[4] * 3600 + +m[5] * 60 + +m[6];
      const jdF = jdn - 0.5 + secs / 86400.0;   // 连续天文 JD（该 UT 时刻）
      // Cesium 的 dayNumber 从「正午」起算（天文约定）：secondsOfDay = JD 小数部分
      const jdnI = Math.floor(jdF);
      v = new Cesium.JulianDate(jdnI, (jdF - jdnI) * 86400.0);
    } else {
      try { v = Cesium.JulianDate.fromIso8601(iso); } catch (e) { v = null; }
    }
    if (v && !isFinite(v.secondsOfDay)) v = null;
    _isoJD.set(iso, v);
    return v;
  }

  /* 日期工具：直接接收 Cesium.JulianDate，与原版实现一致。
     不使用 Date.toISOString()，避免历史年份（含公元前）触发 RangeError: invalid date。
     所有取分量均做有效性兜底。 */
  const util = {
    _date(jd) {
      if (!jd) return null;
      try {
        // 兼容两种入参：Cesium.JulianDate 对象，或 ISO 时间串（如 timeRange.maxEclipse）。
        let j = typeof jd === 'string' ? J(jd) : jd;
        if (!j) return null;
        const d = Cesium.JulianDate.toDate(j);
        return (d && !isNaN(d.getTime())) ? d : null;
      } catch (e) { return null; }
    },
    fmtDateTime(jd) {
      const d = this._date(jd);
      if (!d) return '—';
      const y = d.getUTCFullYear();
      const yTxt = y > 0 ? String(y).padStart(4, '0') : `前${1 - y}年`;
      return `${yTxt}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ` +
             `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())} UTC`;
    },
    fmtUTC(jd) {
      const d = this._date(jd);
      return d ? `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}` : '—:-';
    },
    localApparent(jd, lon) {
      const d = this._date(jd);
      if (!d) return '—:-';
      const t = new Date(d.getTime() + (lon / 15) * 3600 * 1000);
      if (isNaN(t.getTime())) return '—:-';
      return `${pad2(t.getUTCHours())}:${pad2(t.getUTCMinutes())}`;
    }
  };

  /* ---------- 全局状态 ---------- */
  const state = {
    dynKey: null, cfg: null, records: [], id: null,
    tab: 'all', chips: new Set(), q: '',
    minutes: 0, dragging: false, spinning: false
  };

  function currentCfg() { return state.cfg; }
  function recById(id) { return state.records.find(r => r.id === id) || null; }
  function current() { return recById(state.id); }

  /* ================= Cesium 初始化 ================= */
  const viewer = new Cesium.Viewer('cesium', {
    imageryProvider: false,
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, infoBox: false,
    selectionIndicator: false, fullscreenButton: false, vrButton: false,
    skyBox: false, skyAtmosphere: false, scene3DOnly: true,
    creditContainer: document.createElement('div'), requestRenderMode: false
  });
  window.__VIEWER__ = viewer;   // 调试/测试钩子
  const scene = viewer.scene;
  scene.backgroundColor = Cesium.Color.fromCssColorString('#070604');
  scene.globe.baseColor = Cesium.Color.fromCssColorString('#51422c');
  scene.globe.showGroundAtmosphere = false;
  scene.globe.enableLighting = false;
  scene.globe.showWaterEffect = false;
  scene.fog.enabled = false;
  if (scene.sun) scene.sun.show = false;
  if (scene.moon) scene.moon.show = false;
  if (scene.skyBox) scene.skyBox.show = false;
  scene.screenSpaceCameraController.minimumZoomDistance = 1.2e6;
  scene.screenSpaceCameraController.maximumZoomDistance = 6.0e7;

  /* 窗口尺寸变化时同步 canvas（Cesium 自身监听 window resize；此处兜住布局延迟） */
  const resizeCesium = () => { try { viewer.resize(); } catch (e) { /* 布局未就绪 */ } };
  window.addEventListener('resize', resizeCesium);
  requestAnimationFrame(() => requestAnimationFrame(resizeCesium));

  try {
    if (window.__LAND_TEX__) {
      viewer.imageryLayers.addImageryProvider(new Cesium.SingleTileImageryProvider({
        url: window.__LAND_TEX__,
        rectangle: Cesium.Rectangle.fromDegrees(-180, -90, 180, 90),
        tileWidth: 2048, tileHeight: 1024
      }));
    }
  } catch (e) { console.warn('底纹加载失败', e); }

  /* 经纬网（常驻） */
  (function buildGrid() {
    const col = Cesium.Color.fromCssColorString('#c4a878').withAlpha(0.10);
    for (let lon = -180; lon < 180; lon += 15) {
      const arr = [];
      for (let lat = -80; lat <= 80; lat += 5) arr.push(lon, lat);
      viewer.entities.add({ polyline: { positions: Cesium.Cartesian3.fromDegreesArray(arr), width: 1, material: col, arcType: Cesium.ArcType.GEODESIC } });
    }
    for (let lat = -60; lat <= 60; lat += 15) {
      const arr = [];
      for (let lon = -180; lon <= 180; lon += 5) arr.push(lon, lat);
      viewer.entities.add({ polyline: { positions: Cesium.Cartesian3.fromDegreesArray(arr), width: 1, material: col, arcType: Cesium.ArcType.GEODESIC } });
    }
  })();

  /* ---------- 单条日食图层 ---------- */
  const layer = { entities: [], dyn: null };
  function clearLayer() {
    layer.entities.forEach(e => viewer.entities.remove(e));
    layer.entities = [];
    if (layer.dyn) {
      Object.keys(layer.dyn).forEach(k => layer.dyn[k] && viewer.entities.remove(layer.dyn[k]));
      layer.dyn = null;
    }
  }

  function diamondURI(color) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">` +
      `<rect x="4.6" y="4.6" width="6.6" height="6.6" transform="rotate(45 8 8)" fill="none" stroke="${color}" stroke-width="1.7"/></svg>`;
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }
  const DIAMOND = {
    record: diamondURI('#d9c9a8'), center: diamondURI('#8f7a55'), hidden: diamondURI('#877a63')
  };

  function centerOf(rec) {
    if (rec.center && isFinite(rec.center.lon) && isFinite(rec.center.lat)) return rec.center;
    const line = rec.centralLine || [];
    if (line.length) return { lon: line[Math.floor(line.length / 2)][0], lat: line[Math.floor(line.length / 2)][1] };
    const p = (rec.stations || [])[0];
    if (p) return { lon: p.lon, lat: p.lat };
    return { lon: 0, lat: 20 };
  }

  /* 逐帧月影插值（宋：有 shadowFrames） */
  function shadowAt(rec, jd) {
    const f = rec.shadowFrames || [];
    if (!f.length) return null;
    const t0 = J(f[0].t);
    const t1 = J(f[f.length - 1].t);
    // 防御：时间串格式异常会让解析返回无效值，
    // secondsDifference 得 NaN，进而 f[NaN]=undefined 抛错并中断 Cesium 渲染循环。
    if (!t0 || !t1 || !isFinite(t0.secondsOfDay) || !isFinite(t1.secondsOfDay)) return null;
    const total = Cesium.JulianDate.secondsDifference(t1, t0);
    if (!(total > 0)) return null;
    const s = Cesium.Math.clamp(Cesium.JulianDate.secondsDifference(jd, t0), 0, total) / total;
    if (!isFinite(s)) return null;
    const x = s * (f.length - 1);
    const i = Math.max(0, Math.min(f.length - 2, Math.floor(x))), k = x - i;
    const a = f[i], b = f[Math.min(i + 1, f.length - 1)];
    if (!a || !b || !isFinite(a.lon) || !isFinite(b.lon)) return null;
    let dLon = b.lon - a.lon;
    if (dLon > 180) dLon -= 360; if (dLon < -180) dLon += 360;
    return {
      lat: a.lat + (b.lat - a.lat) * k,
      lon: a.lon + dLon * k,
      r: a.r + (b.r - a.r) * k,
      alt: Math.max(0.6, a.alt + (b.alt - a.alt) * k)
    };
  }

  function azimuth(lon1, lat1, lon2, lat2) {
    const p1 = Cesium.Math.toRadians(lat1), p2 = Cesium.Math.toRadians(lat2);
    const dl = Cesium.Math.toRadians(lon2 - lon1);
    const y = Math.sin(dl) * Math.cos(p2);
    const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
    return Math.atan2(y, x);
  }

  /* 当前时刻的影心：绝对时间轴走 shadowAt；相对时间轴走 center + minutes */
  function shadowNow(rec) {
    const mode = currentCfg().rangeMode;
    if (mode === 'absolute') return shadowAt(rec, viewer.clock.currentTime);
    // 相对分钟（汉版无几何）：影心沿纬线东西移动 0.25°/分（±90′ → ±22.5°）。
    // r 为示意本影半径(km)，随食分放大；适配 12500km 相机高度，避免亚像素不可见。
    const c = centerOf(rec);
    const mag = rec.extra && isFinite(rec.extra.mag) ? rec.extra.mag : 0.5;
    const r = 70 + mag * 110;   // 约 100~180 km，半影为其 7.2 倍
    return { lon: c.lon + state.minutes * 0.25, lat: c.lat, r: r, alt: 30, bearing: 0 };
  }

  /* 汉版示意中心线的经度跨度：±90′ × 0.25°/分 = ±22.5° */
  const REL_LON_SPAN = 90 * 0.25;
  function relTrackPoints(rec, fromMin, toMin, step) {
    const c = centerOf(rec), pts = [];
    for (let m = fromMin; m < toMin; m += step) pts.push(c.lon + m * 0.25, c.lat);
    pts.push(c.lon + toMin * 0.25, c.lat);
    return pts.length >= 4 ? Cesium.Cartesian3.fromDegreesArray(pts) : [];
  }

  const VIEW_ALT = 1.25e7;
  function flyCenter(rec) {
    // 自转的逐帧 rotate 会与 flyTo 叠加、导致相机飞不到影心（轨迹落在地球背面看不见）。
    // 定位前先停自转，确保相机稳定对准影心。
    setSpin(false);
    const c = centerOf(rec);
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(c.lon, c.lat, VIEW_ALT),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 },
      duration: 1.5
    });
  }

  /* ================= 图层装配 ================= */
  function loadEclipse(rec) {
    clearLayer();
    if (!rec) return;
    const clr = Cesium.Color.fromCssColorString(TYPE_COLOR[rec.type] || '#d9b16a');
    const hasGeom = !!(rec.shadowFrames && rec.shadowFrames.length);

    /* 半影多边形不再渲染：半影扫掠包络/食甚落区跨数千公里，叠 0.26 暗色后
       呈现为「大黑带/大黑斑」，与视觉噪声无异（2026-11-19 用户反馈）。
       半影信息由动态半影椭圆（当前位置）承担；数据保留在记录中。 */
    /* 本影 / 伪本影多边形 */
    if (rec.umbraPolygon && rec.umbraPolygon.length > 3) {
      layer.entities.push(viewer.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(Cesium.Cartesian3.fromDegreesArray(rec.umbraPolygon)),
          material: Cesium.Color.fromCssColorString('#050403').withAlpha(0.5),
          outline: true, outlineColor: clr.withAlpha(0.5), outlineWidth: 1
        }
      }));
    }
    /* 中心线 */
    if (rec.centralLine && rec.centralLine.length > 1) {
      layer.entities.push(viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(rec.centralLine.flat()),
          width: 1.4, arcType: Cesium.ArcType.GEODESIC,
          material: Cesium.Color.fromCssColorString('#cfc4ab').withAlpha(0.35)
        }
      }));
    }
    /* 观测点 */
    (rec.stations || []).forEach(p => {
      layer.entities.push(viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(p.lon, p.lat),
        billboard: {
          image: p.visible ? DIAMOND.record : DIAMOND.hidden,
          scale: p.visible ? 0.9 : 0.7,
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        },
        label: {
          text: p.name, font: '11px "Noto Serif SC", serif',
          fillColor: Cesium.Color.fromCssColorString(p.visible ? '#e7d9b8' : '#877a63'),
          style: Cesium.LabelStyle.FILL, showBackground: true,
          backgroundColor: Cesium.Color.fromCssColorString('#0a0d12').withAlpha(0.55),
          backgroundPadding: new Cesium.Cartesian2(4, 2),
          pixelOffset: new Cesium.Cartesian2(0, -16),
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        }
      }));
    });
    /* 食甚中心 */
    const c = centerOf(rec);
    layer.entities.push(viewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(c.lon, c.lat),
      billboard: { image: DIAMOND.center, scale: 1.0, disableDepthTestDistance: Number.POSITIVE_INFINITY },
      label: {
        text: `食甚中心 ${dmsLabel(c.lat, 'N', 'S')} / ${dmsLabel(c.lon, 'E', 'W')}`,
        font: '10.5px "Noto Sans SC", sans-serif',
        fillColor: Cesium.Color.fromCssColorString('#9d8e74'),
        outlineColor: Cesium.Color.fromCssColorString('#0a0805'), outlineWidth: 2,
        pixelOffset: new Cesium.Cartesian2(0, 16),
        disableDepthTestDistance: Number.POSITIVE_INFINITY
      }
    }));

    /* 动态月影：有逐帧用 CallbackProperty 跟随 clock；无逐帧用 relative 状态 */
    const posProp = new Cesium.CallbackProperty(() => {
      const s = shadowNow(rec);
      return s ? Cesium.Cartesian3.fromDegrees(s.lon, s.lat) : undefined;
    }, false);
    layer.dyn = {};
    layer.dyn.penumbra = viewer.entities.add({
      position: posProp,
      ellipse: {
        semiMajorAxis: new Cesium.CallbackProperty(() => { const s = shadowNow(rec); return s ? s.r * 1000 * 7.2 : 1; }, false),
        semiMinorAxis: new Cesium.CallbackProperty(() => { const s = shadowNow(rec); return s ? s.r * 1000 * 7.2 : 1; }, false),
        material: Cesium.Color.fromCssColorString('#050403').withAlpha(0.16), height: 0
      }
    });
    layer.dyn.umbra = viewer.entities.add({
      position: posProp,
      ellipse: {
        semiMinorAxis: new Cesium.CallbackProperty(() => { const s = shadowNow(rec); return s ? Math.max(s.r * 1000, 3000) : 1; }, false),
        semiMajorAxis: new Cesium.CallbackProperty(() => {
          const s = shadowNow(rec); if (!s) return 1;
          return Math.max(s.r * 1000, 3000) / Math.max(0.12, Math.sin(Cesium.Math.toRadians(Math.min(s.alt || 30, 80))));
        }, false),
        material: Cesium.Color.fromCssColorString('#030302').withAlpha(0.78),
        outline: true, outlineColor: clr.withAlpha(0.55), height: 0
      }
    });
    /* 汉版示意轨迹：无逐帧几何，按相对分钟 ±90′ 构造一条沿纬线的示意影带中心线。
       注意这是"示意"——表示月影扫过的大致方向与范围，非精确几何路径。 */
    if (!hasGeom && currentCfg().rangeMode === 'relative') {
      const c = centerOf(rec);
      // 全程虚线（T-90′ → T+90′）
      layer.entities.push(viewer.entities.add({
        polyline: {
          positions: Cesium.Cartesian3.fromDegreesArray(
            (() => { const p = []; for (let m = -90; m <= 90; m += 6) p.push(c.lon + m * 0.25, c.lat); return p; })()
          ),
          width: 1.2, arcType: Cesium.ArcType.GEODESIC,
          material: new Cesium.PolylineDashMaterialProperty({
            color: Cesium.Color.fromCssColorString('#cfc4ab').withAlpha(0.4), dashLength: 9
          })
        }
      }));
      // 已扫过高亮段（T-90′ → 当前分钟），随时间轴增长
      layer.dyn.progress = viewer.entities.add({
        polyline: {
          positions: new Cesium.CallbackProperty(() => relTrackPoints(rec, -90, state.minutes, 3), false),
          width: 3.4, arcType: Cesium.ArcType.GEODESIC,
          material: new Cesium.PolylineGlowMaterialProperty({
            glowPower: 0.16, taperPower: 0.55, color: Cesium.Color.fromCssColorString('#f6efdc')
          })
        }
      });
      // 影带示意椭圆（沿移动方向拉长的半透明带，覆盖中心点前后一段经度）
      layer.entities.push(viewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(c.lon, c.lat),
        ellipse: {
          semiMinorAxis: 90000, semiMajorAxis: 620000,
          rotation: Cesium.Math.toRadians(90), height: 0,
          material: Cesium.Color.fromCssColorString('#050403').withAlpha(0.2),
          outline: true, outlineColor: Cesium.Color.fromCssColorString('#d9b16a').withAlpha(0.28)
        }
      }));
    }

    /* 已扫过轨迹（仅绝对时间轴且逐帧时） */
    if (hasGeom && currentCfg().rangeMode === 'absolute') {
      layer.dyn.progress = viewer.entities.add({
        polyline: {
          positions: new Cesium.CallbackProperty(() => {
            const t = viewer.clock.currentTime, pts = [];
            for (const q of rec.shadowFrames) {
              if (Cesium.JulianDate.greaterThan(J(q.t), t)) break;
              pts.push(q.lon, q.lat);
            }
            const s = shadowAt(rec, t);
            if (s) pts.push(s.lon, s.lat);
            return pts.length > 3 ? Cesium.Cartesian3.fromDegreesArray(pts) : [];
          }, false),
          width: 3.2, arcType: Cesium.ArcType.GEODESIC,
          material: new Cesium.PolylineGlowMaterialProperty({ glowPower: 0.13, taperPower: 0.7, color: Cesium.Color.fromCssColorString('#f6efdc') })
        }
      });
    }

    /* 时间轴装配 */
    setupClock(rec, hasGeom);
    renderTicks(rec);
  }

  function dmsLabel(v, pos, neg) {
    if (v === null || v === undefined || !isFinite(v)) return '—';
    return Math.abs(v).toFixed(1) + '°' + (v >= 0 ? pos : neg);
  }

  /* ================= 时间轴 ================= */
  const rangeEl = $('#timeRange');
  function setupClock(rec, hasGeom) {
    if (currentCfg().rangeMode === 'absolute' && rec.timeRange && rec.timeRange.start) {
      const t0 = J(rec.timeRange.start);
      const tm = J(rec.timeRange.maxEclipse);
      const t1 = J(rec.timeRange.end);
      if (!t0 || !tm || !t1) { viewer.clock.shouldAnimate = false; state.minutes = 0; syncTimeUI(); return; }
      viewer.clock.startTime = t0.clone();
      viewer.clock.stopTime = t1.clone();
      viewer.clock.currentTime = tm.clone();
      viewer.clock.clockRange = Cesium.ClockRange.CLAMPED;
      viewer.clock.clockStep = Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER;
      viewer.clock.multiplier = 900;
      viewer.clock.shouldAnimate = false;
    } else {
      viewer.clock.shouldAnimate = false;
      state.minutes = 0;
    }
    syncTimeUI();
  }

  function renderTicks(rec) {
    const tk = $('#ticks'); tk.innerHTML = '';
    if (currentCfg().rangeMode === 'relative') {
      ['−90′', '食甚', '+90′'].forEach((label, i) => {
        const s = document.createElement('span'); s.textContent = label;
        if (i === 0) s.style.left = '0';
        else if (i === 2) s.style.right = '0';
        else { s.style.left = '50%'; s.style.transform = 'translateX(-50%)'; }
        tk.appendChild(s);
      });
    } else {
      ['初亏', '食甚', '复圆'].forEach((label, i) => {
        const s = document.createElement('span'); s.textContent = label;
        if (i === 0) s.style.left = '0';
        else if (i === 2) s.style.right = '0';
        else { s.style.left = '50%'; s.style.transform = 'translateX(-50%)'; }
        tk.appendChild(s);
      });
    }
  }

  function syncTimeUI() {
    const rec = current(); if (!rec) return;
    let offText, clockText;
    if (currentCfg().rangeMode === 'relative') {
      offText = state.minutes === 0 ? 'T ± 0 分' : (state.minutes > 0 ? '+' : '') + state.minutes + ' 分';
      clockText = '相对食甚时刻 · 影心东西移动';
    } else {
      const c = centerOf(rec);
      const t = viewer.clock.currentTime;
      let tm;
      if (rec.timeRange && rec.timeRange.maxEclipse) tm = J(rec.timeRange.maxEclipse);
      if (!tm) tm = t;
      const offMin = isNaN(Cesium.JulianDate.secondsDifference(t, tm)) ? 0 : Math.round(Cesium.JulianDate.secondsDifference(t, tm) / 60);
      offText = offMin === 0 ? '食甚' : `食甚 ${offMin > 0 ? '+' : '−'}${Math.abs(offMin)}m`;
      // 直接传 JulianDate（BC 年份的 toISOString 会带毫秒并经格里历重解释，不可用）
      clockText = `${util.fmtUTC(t)} UTC ／ ${util.localApparent(t, c.lon || 0)} 视时`;
      if (!state.dragging && rec.timeRange && rec.timeRange.start) {
        const t0 = J(rec.timeRange.start);
        const t1 = J(rec.timeRange.end);
        const total = (t0 && t1) ? Cesium.JulianDate.secondsDifference(t1, t0) : NaN;
        if (total > 0) rangeEl.value = Math.round(Cesium.Math.clamp(Cesium.JulianDate.secondsDifference(t, t0) / total, 0, 1) * 1000);
      }
    }
    $('#offsetLabel').textContent = offText;
    $('#clockLabel').textContent = clockText;
  }

  rangeEl.addEventListener('pointerdown', () => { state.dragging = true; });
  rangeEl.addEventListener('pointerup', () => { state.dragging = false; });
  rangeEl.addEventListener('input', () => {
    const rec = current(); if (!rec) return;
    if (currentCfg().rangeMode === 'relative') {
      state.minutes = Math.round((+rangeEl.value / 1000) * 180 - 90);
      syncTimeUI();
    } else if (rec.timeRange && rec.timeRange.start && J(rec.timeRange.start) && J(rec.timeRange.end)) {
      const t0 = J(rec.timeRange.start);
      const t1 = J(rec.timeRange.end);
      const total = Cesium.JulianDate.secondsDifference(t1, t0);
      viewer.clock.currentTime = Cesium.JulianDate.addSeconds(t0, total * (+rangeEl.value / 1000), new Cesium.JulianDate());
      syncTimeUI();
    }
  });
  $('#playBtn').addEventListener('click', () => {
    if (currentCfg().rangeMode === 'relative') return; // 相对模式不做自动播放
    viewer.clock.shouldAnimate = !viewer.clock.shouldAnimate;
    const playing = viewer.clock.shouldAnimate;
    $('#playIcon').innerHTML = playing
      ? '<rect x="0" y="0" width="3.4" height="12" fill="#d9b16a"/><rect x="6.6" y="0" width="3.4" height="12" fill="#d9b16a"/>'
      : '<path d="M0 0l10 6-10 6z" fill="#d9b16a"/>';
  });
  viewer.clock.onTick.addEventListener(() => { if (currentCfg() && currentCfg().rangeMode === 'absolute') syncTimeUI(); });

  /* ================= 视角控制 ================= */
  scene.postRender.addEventListener(() => {
    if (!state.spinning) return;
    viewer.camera.rotate(Cesium.Cartesian3.UNIT_Z, Cesium.Math.toRadians(-0.18));
  });
  function setSpin(on) {
    state.spinning = on;
    $('#modeSpin').classList.toggle('on', on);
    if (on) $('#modeCenter').classList.remove('on');
  }
  $('#modeCenter').addEventListener('click', () => { setSpin(false); $('#modeCenter').classList.add('on'); flyCenter(current()); });
  $('#modeSpin').addEventListener('click', () => setSpin(!state.spinning));
  $('#modeReset').addEventListener('click', () => {
    setSpin(false);
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(-40, 25, 2.2e7),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 }, duration: 1.4
    });
  });

  /* ================= 筛选 / 列表 ================= */
  function matchFilter(r) {
    if (state.tab !== 'all' && r.type !== state.tab) return false;
    for (const key of state.chips) {
      const chip = state.cfg.chips.find(c => c.key === key);
      if (chip && !chip.test(r)) return false;
    }
    if (state.q) {
      const fields = state.cfg.searchFields || ['id', 'dateLabel', 'text'];
      const hay = fields.map(f => r[f] != null ? r[f] : '').join(' ').toLowerCase();
      if (!hay.includes(state.q.toLowerCase())) return false;
    }
    return true;
  }

  function badgeOf(r) {
    if (r.flags.includes('noEat')) return '云阴';
    if (r.flags.includes('cloudHide')) return '云阴';
    return TYPE_LABEL[r.type] || r.type || '—';
  }

  function renderList() {
    const list = $('#list'); list.innerHTML = '';
    const shown = state.records.filter(matchFilter);
    if (!shown.length) {
      list.innerHTML = '<div class="list-empty">没有符合筛选的条目<br>请放宽条件或更换筛选</div>';
      return;
    }
    shown.forEach(r => {
      const row = document.createElement('div');
      row.className = 'row' + (r.id === state.id ? ' on' : '');
      const meta = r.era || '';
      const idText = state.cfg.listId ? state.cfg.listId(r.id) : r.id;
      const dateText = state.cfg.listDate ? state.cfg.listDate(r.dateLabel) : r.dateLabel;
      row.innerHTML = `<span class="idx num">${idText}</span>
        <span class="date num">${dateText}</span>
        <span class="meta">${meta}</span>
        <span class="badge b-${r.type}">${badgeOf(r)}</span>`;
      row.addEventListener('click', () => selectRecord(r.id, true));
      list.appendChild(row);
    });
    const on = list.querySelector('.row.on');
    if (on) on.scrollIntoView({ block: 'nearest' });
  }

  function renderCounters() {
    const tabs = $$('#typeTabs .tab');
    tabs.forEach(t => {
      const k = t.dataset.type;
      const b = t.querySelector('b'); if (!b) return;
      b.textContent = k === 'all' ? state.records.length : state.records.filter(r => r.type === k).length;
    });
    $$('#flagChips .chip').forEach(btn => {
      const chip = state.cfg.chips.find(c => c.key === btn.dataset.flag);
      const b = btn.querySelector('b');
      if (b && chip) b.textContent = state.records.filter(chip.test).length;
    });
    $('#loadedCount').textContent = state.records.length;
  }

  /* ================= 顶栏 / 控制面板 ================= */
  function renderDynastyButtons() {
    const bar = $('#dynastyButtons'); bar.innerHTML = '';
    window.__DYNASTIES__.forEach(d => {
      const b = document.createElement('button');
      b.className = 'dyn-btn' + (d.key === state.dynKey ? ' on' : '');
      b.textContent = d.label;
      b.title = d.title;
      b.addEventListener('click', () => switchDynasty(d.key));
      bar.appendChild(b);
    });
  }

  function renderFilterControls() {
    const tabs = $('#typeTabs'); tabs.innerHTML = '';
    state.cfg.tabs.forEach(t => {
      const b = document.createElement('button');
      b.className = 'tab' + (t.key === state.tab ? ' on' : '');
      b.dataset.type = t.key;
      b.innerHTML = `${t.label} <b>0</b>`;
      tabs.appendChild(b);
    });
    const chips = $('#flagChips'); chips.innerHTML = '';
    state.cfg.chips.forEach(c => {
      const b = document.createElement('button');
      b.className = 'chip';
      b.dataset.flag = c.key;
      b.innerHTML = `${c.label} <b>0</b>`;
      chips.appendChild(b);
    });
    // 绑定事件（每次重建，旧节点已销毁）
    $$('#typeTabs .tab').forEach(btn => btn.addEventListener('click', () => {
      $$('#typeTabs .tab').forEach(b => b.classList.remove('on'));
      btn.classList.add('on'); state.tab = btn.dataset.type; renderList();
    }));
    $$('#flagChips .chip').forEach(btn => btn.addEventListener('click', () => {
      const k = btn.dataset.flag;
      if (state.chips.has(k)) { state.chips.delete(k); btn.classList.remove('on'); }
      else { state.chips.add(k); btn.classList.add('on'); }
      renderList();
    }));
  }

  /* ================= 详情方法论弹窗 ================= */
  /* 顶栏按钮统一为「放大详情」：点击后在浮层中放大展示右侧详情面板。
     方法论内容（原文与判定分层）保留入口：详情里的「回原核查页」链接，
     无论在右栏还是浮层中点击，都会把浮层切换为方法论内容。 */
  function setupMethodology() {
    const btn = $('#methodBtn');
    btn.style.display = '';
    btn.textContent = '放大详情';
  }
  function openMethodology() {
    if (!state.cfg || !state.cfg.methodology) return;
    $('#modalTitle').textContent = state.cfg.methodology.title || '判定与数据处理';
    $('#modalBody').innerHTML = renderMethodology(state.cfg);
    $('#modal .sheet').classList.remove('zoom');
    $('#modal').classList.add('on');
  }
  /* 放大详情：把当前右栏详情的渲染结果复制到浮层，加宽浮层呈现「放大版」。
     复制出的「回原核查页」改名（避免与右栏同 ID 冲突），点击后浮层切换为方法论。 */
  function openDetailZoom() {
    const rec = current();
    if (!rec) return;
    const body = $('#modalBody');
    body.innerHTML = $('#detail').innerHTML;
    const link = body.querySelector('.d-link');
    if (link) {
      link.id = 'openSheetZoom';
      link.addEventListener('click', openMethodology);
    }
    $('#modalTitle').textContent = `${state.cfg.label} · 第 ${rec.id} 条 · 详情放大`;
    $('#modal .sheet').classList.add('zoom');
    $('#modal').classList.add('on');
  }
  $('#methodBtn').addEventListener('click', openDetailZoom);
  $('#modalClose').addEventListener('click', () => $('#modal').classList.remove('on'));
  $('#modal').addEventListener('click', e => { if (e.target === $('#modal')) $('#modal').classList.remove('on'); });

  /* ================= 选中联动 ================= */
  function selectRecord(id, fly) {
    const rec = recById(id); if (!rec) return;
    state.id = id;
    loadEclipse(rec);
    renderList();
    renderDetail();
    renderTopChip(rec);
    syncTimeUI();
    if (fly) flyCenter(rec);
  }

  function renderDetail() {
    const rec = current();
    const el = $('#detail');
    if (!rec) { el.innerHTML = '<div class="empty-detail">未选中条目</div>'; return; }
    const fn = RENDERERS[state.cfg.renderer] || RENDERERS.astronomical;
    el.innerHTML = fn(rec, state.cfg, util);
    const link = $('#openSheet');
    if (link) link.addEventListener('click', openMethodology);
    el.scrollTop = 0;
  }

  function renderTopChip(rec) {
    const chip = $('#topChip');
    if (currentCfg().rangeMode === 'relative') {
      const c = centerOf(rec);
      chip.innerHTML = `<em>${rec.dateLabel}</em> ${rec.text ? rec.text.slice(0, 26) : ''} · 影心 <em>${dmsLabel(c.lat, 'N', 'S')} ${dmsLabel(c.lon, 'E', 'W')}</em>`;
      return;
    }
    const vis = (rec.stations || []).filter(p => p.visible);
    if (rec.flags.includes('cloudHide')) {
      chip.innerHTML = `<em>${rec.dateLabel}</em> 古籍记「云阴不见」，影带实自 <em>${dmsLabel(centerOf(rec).lat, 'N', 'S')} ${dmsLabel(centerOf(rec).lon, 'E', 'W')}</em> 扫过`; return;
    }
    if (rec.flags.includes('noEat')) { chip.innerHTML = `<em>${rec.dateLabel}</em> 古籍记「当食不食」，回推影带亦不在境内`; return; }
    if (rec.flags.includes('noEclipse')) { chip.innerHTML = `<em>${rec.dateLabel}</em> NASA 目录该日无食 —— 推步虚报或历日传讹，如实降级标注`; return; }
    if (!vis.length) { chip.innerHTML = `<em>${rec.dateLabel}</em> 影带中心 <em>${dmsLabel(centerOf(rec).lat, 'N', 'S')} ${dmsLabel(centerOf(rec).lon, 'E', 'W')}</em>，观测点当日太阳在地平线下`; return; }
    const p = vis[0];
    const tmIso = rec.timeRange && rec.timeRange.maxEclipse;
    chip.innerHTML = `<em>${p.name}</em> 这次看得见 ${tmIso ? util.localApparent(tmIso, p.lon) : '—'} 前后食甚，食分 ${(p.obsc || 0).toFixed(2)}`;
  }

  /* ================= 朝代切换 ================= */
  function sortRecords(list) {
    return list.slice().sort((a, b) => {
      const d = (a.sortKey || 0) - (b.sortKey || 0);
      return d !== 0 ? d : String(a.id || '').localeCompare(String(b.id || ''));
    });
  }

  function switchDynasty(key) {
    const cfg = window.__DYNASTIES__.find(d => d.key === key);
    const pack = (window.__ECLIPSE_DATA__ || {})[cfg ? cfg.dataKey : key];
    if (!cfg || !pack) { console.warn('朝代数据缺失', key); return; }
    setSpin(false);
    state.dynKey = key;
    state.cfg = cfg;
    state.records = sortRecords(pack.records || []);
    state.tab = 'all';
    state.chips.clear();
    state.q = '';
    $('#searchInput').value = '';

    // 标题 / 副标题 / 图例标题
    // 统一标题格式：[朝代]日食 · [数量]条（如「宋日食 · 225条」）
    $('#appTitle').textContent = `${cfg.label}日食 · ${state.records.length}条`;
    $('#appSubtitle').textContent = cfg.subtitle;
    $('#legendTitle').textContent = currentCfg().rangeMode === 'relative' ? '月影落区（点位降级 · 示意）' : '月影（越黑＝遮得越多）';
    $('#legendNote').style.display = currentCfg().rangeMode === 'relative' ? '' : 'none';

    renderDynastyButtons();
    renderFilterControls();
    setupMethodology();
    renderCounters();

    // 首屏记录
    let start = null;
    if (cfg.initialRecord) start = state.records.find(r => r.dateLabel === cfg.initialRecord || r.id === cfg.initialRecord);
    if (!start) start = state.records[0];
    if (start) {
      state.id = start.id;
      selectRecord(start.id, false);
      const c = centerOf(start);
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(c.lon, c.lat, VIEW_ALT),
        orientation: { heading: 0, pitch: Cesium.Math.toRadians(-90), roll: 0 }
      });
    } else {
      $('#topChip').textContent = '该朝代暂无日食数据';
      $('#detail').innerHTML = '<div class="empty-detail">暂无数据</div>';
      clearLayer();
    }
  }

  /* ================= 搜索 / JSON 导入 ================= */
  $('#searchInput').addEventListener('input', e => { state.q = e.target.value.trim(); renderList(); });
  $('#importFile').addEventListener('change', e => {
    const file = e.target.files && e.target.files[0]; if (!file) return;
    const fr = new FileReader();
    fr.onload = () => {
      try {
        const parsed = JSON.parse(fr.result);
        const list = Array.isArray(parsed) ? parsed : (parsed.records || []);
        if (!list.length) throw new Error('没有可用条目');
        state.records = sortRecords(list);
        state.tab = 'all'; state.chips.clear(); state.q = '';
        renderFilterControls(); renderCounters();
        state.id = state.records[0].id;
        selectRecord(state.records[0].id, true);
        toast(`已载入 ${list.length} 条，按 sortKey 升序排列`);
      } catch (err) { toast('JSON 解析失败：' + err.message); console.error(err); }
    };
    fr.readAsText(file, 'utf-8');
    e.target.value = '';
  });
  function toast(msg) {
    const el = $('#toast'); el.textContent = msg; el.classList.add('on');
    clearTimeout(toast._t); toast._t = setTimeout(() => el.classList.remove('on'), 2200);
  }

  /* ================= 启动 ================= */
  if (!window.__DYNASTIES__ || !window.__DYNASTIES__.length) {
    $('#topChip').textContent = '未注册任何朝代';
    console.error('DYNASTIES 为空');
    return;
  }
  const first = new URLSearchParams(location.search).get('dynasty');
  const defaultDyn = window.__DYNASTIES__.find(d => d.isDefault) || window.__DYNASTIES__[0];
  const startKey = window.__DYNASTIES__.some(d => d.key === first) ? first : defaultDyn.key;
  switchDynasty(startKey);

  // 暴露给外部：便于 ?dynasty=han&rec=xxx 直达
  const deepRec = new URLSearchParams(location.search).get('rec');
  if (deepRec && recById(deepRec)) selectRecord(deepRec, true);
  window.__ECLIPSE_APP__ = { switchDynasty, state };
})();

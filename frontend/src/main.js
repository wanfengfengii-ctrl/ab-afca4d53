import { cycleClosures } from './loops.js';

const STATION_LIMIT = 10;
const STATION_MIN = 5;
const OBS_LIMIT = 18;
const OBS_MIN = 7;

const SAMPLE = {
  stations: [
    { name: 'A', benchmark: true },
    { name: 'B', benchmark: false },
    { name: 'C', benchmark: false },
    { name: 'D', benchmark: false },
    { name: 'E', benchmark: false },
  ],
  benchmarkHeight: 1000,
  observations: [
    { start: 'A', end: 'B', delta: 125, limit: 3 },
    { start: 'B', end: 'A', delta: -124, limit: 3 },
    { start: 'B', end: 'C', delta: -230, limit: 3 },
    { start: 'C', end: 'B', delta: 231, limit: 3 },
    { start: 'C', end: 'D', delta: 87, limit: 3 },
    { start: 'D', end: 'E', delta: -56, limit: 3 },
    { start: 'E', end: 'A', delta: 75, limit: 3 },
  ],
};

let draft = structuredClone(SAMPLE);
let result = null;

const $ = (id) => document.getElementById(id);

function markDirty() {
  // Editing the draft immediately invalidates any prior conclusion.
  result = null;
  $('resultPanel').hidden = true;
  $('draftHint').hidden = false;
}

function renderStations() {
  const body = $('stationsBody');
  body.innerHTML = '';
  draft.stations.forEach((s, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><input data-k="name" value="${s.name}" maxlength="20" /></td>
      <td><input type="radio" name="benchmark" data-k="benchmark" ${s.benchmark ? 'checked' : ''} /></td>
      <td><button type="button" class="danger" data-act="del">删除</button></td>`;
    tr.querySelector('[data-k="name"]').addEventListener('input', (ev) => {
      const oldName = s.name;
      s.name = ev.target.value;
      // Keep observation endpoints pointing at the renamed station.
      for (const o of draft.observations) {
        if (o.start === oldName) o.start = s.name;
        if (o.end === oldName) o.end = s.name;
      }
      renderObservations();
      markDirty();
    });
    tr.querySelector('[data-k="benchmark"]').addEventListener('change', () => {
      draft.stations.forEach((x, j) => (x.benchmark = j === i));
      markDirty();
    });
    tr.querySelector('[data-act="del"]').addEventListener('click', () => {
      draft.stations.splice(i, 1);
      renderAll();
      markDirty();
    });
    body.appendChild(tr);
  });
}

function stationOptions(selected) {
  return draft.stations
    .map((s) => `<option value="${s.name}" ${s.name === selected ? 'selected' : ''}>${s.name}</option>`)
    .join('');
}

function renderObservations() {
  const body = $('observationsBody');
  body.innerHTML = '';
  draft.observations.forEach((o, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><select data-k="start">${stationOptions(o.start)}</select></td>
      <td><select data-k="end">${stationOptions(o.end)}</select></td>
      <td><input data-k="delta" type="number" step="1" value="${o.delta}" /></td>
      <td><input data-k="limit" type="number" step="1" min="0" value="${o.limit}" /></td>
      <td><button type="button" class="danger" data-act="del">删除</button></td>`;
    tr.querySelector('[data-k="start"]').addEventListener('change', (ev) => {
      o.start = ev.target.value;
      markDirty();
    });
    tr.querySelector('[data-k="end"]').addEventListener('change', (ev) => {
      o.end = ev.target.value;
      markDirty();
    });
    tr.querySelector('[data-k="delta"]').addEventListener('input', (ev) => {
      o.delta = ev.target.value === '' ? '' : Number(ev.target.value);
      markDirty();
    });
    tr.querySelector('[data-k="limit"]').addEventListener('input', (ev) => {
      o.limit = ev.target.value === '' ? '' : Number(ev.target.value);
      markDirty();
    });
    tr.querySelector('[data-act="del"]').addEventListener('click', () => {
      draft.observations.splice(i, 1);
      renderAll();
      markDirty();
    });
    body.appendChild(tr);
  });
}

function renderAll() {
  renderStations();
  renderObservations();
}

function validateDraft() {
  const names = draft.stations.map((s) => s.name.trim());
  if (draft.stations.length < STATION_MIN || draft.stations.length > STATION_LIMIT) {
    return `测站数量须在 ${STATION_MIN}–${STATION_LIMIT} 个之间（当前 ${draft.stations.length}）。`;
  }
  if (names.some((n) => !n)) return '存在空的测站名称。';
  if (new Set(names).size !== names.length) return '测站名称必须唯一。';
  if (draft.stations.filter((s) => s.benchmark).length !== 1) return '必须且只能勾选一个基准测站。';
  if (!Number.isInteger(draft.benchmarkHeight)) return '基准高程必须是整数（毫米）。';
  if (draft.observations.length < OBS_MIN || draft.observations.length > OBS_LIMIT) {
    return `观测数量须在 ${OBS_MIN}–${OBS_LIMIT} 条之间（当前 ${draft.observations.length}）。`;
  }
  for (const o of draft.observations) {
    const os = o.start.trim();
    const oe = o.end.trim();
    if (!names.includes(os) || !names.includes(oe)) return '存在引用了未定义测站的观测。';
    if (os === oe) return '观测起点与终点不能相同。';
    if (!Number.isInteger(o.delta)) return '实测高差必须是整数毫米。';
    if (!Number.isInteger(o.limit) || o.limit < 0) return '最大允许改正量必须是非负整数毫米。';
  }
  return null;
}

async function submit() {
  const err = validateDraft();
  if (err) {
    showMessage(err, true);
    return;
  }
  const base = $('apiBase').value.trim().replace(/\/$/, '');
  const trimMap = new Map(draft.stations.map((s) => [s.name, s.name.trim()]));
  const payload = {
    stations: draft.stations.map((s) => ({ name: s.name.trim(), benchmark: s.benchmark })),
    benchmark_height: draft.benchmarkHeight,
    observations: draft.observations.map((o) => ({
      start: trimMap.get(o.start) ?? o.start.trim(),
      end: trimMap.get(o.end) ?? o.end.trim(),
      delta: o.delta,
      limit: o.limit,
    })),
  };
  $('submitBtn').disabled = true;
  try {
    const resp = await fetch(`${base}/api/adjust`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (resp.status === 422) {
      const body = await resp.json();
      const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      showFailure(`输入无法处理：${detail}`);
      return;
    }
    if (!resp.ok) {
      showFailure(`服务异常（HTTP ${resp.status}），请稍后重试。`);
      return;
    }
    result = await resp.json();
    $('draftHint').hidden = true;
    renderResult();
  } catch (e) {
    showFailure(`无法连接 API：${e.message}`);
  } finally {
    $('submitBtn').disabled = false;
  }
}

function showFailure(message) {
  // No feasible adjustment (or request error): keep the draft, clear old
  // results, state clearly that the allowed corrections are insufficient.
  result = null;
  $('resultPanel').hidden = false;
  $('summary').innerHTML = `<div class="banner error">${message}</div>`;
  $('elevationBlock').hidden = true;
  $('correctionBlock').hidden = true;
  $('loopsBlock').hidden = true;
}

function showMessage(message, isError) {
  $('resultPanel').hidden = false;
  $('summary').innerHTML =
    `<div class="banner ${isError ? 'error' : 'ok'}">${message}</div>`;
  $('elevationBlock').hidden = true;
  $('correctionBlock').hidden = true;
  $('loopsBlock').hidden = true;
}

function fmt(v) {
  return Number(v).toLocaleString('zh-CN');
}

function renderResult() {
  const panel = $('resultPanel');
  panel.hidden = false;
  if (!result.feasible) {
    showFailure(
      `${result.message}（草稿已保留，可放宽某些观测的最大允许改正量后重新提交。）`,
    );
    return;
  }
  $('summary').innerHTML = `
    <div class="banner ok">${result.message}</div>
    <div class="metrics">
      <span>最大绝对改正：<b>${fmt(result.max_abs_correction)}</b> mm</span>
      <span>绝对改正总和：<b>${fmt(result.total_abs_correction)}</b> mm</span>
    </div>`;
  $('elevationBlock').hidden = false;
  $('correctionBlock').hidden = false;
  $('loopsBlock').hidden = false;

  $('elevationsBody').innerHTML = result.elevations
    .map(
      (e, i) =>
        `<tr${draft.stations[i].benchmark ? ' class="bm"' : ''}><td>${e.name}${
          draft.stations[i].benchmark ? '（基准）' : ''
        }</td><td>${fmt(e.elevation)}</td></tr>`,
    )
    .join('');

  $('correctionsBody').innerHTML = result.corrections
    .map(
      (c, k) => `
      <tr class="${c.within_limit ? '' : 'over'}">
        <td>${k + 1}</td><td>${c.start}</td><td>${c.end}</td>
        <td>${fmt(c.delta)}</td>
        <td>${c.correction > 0 ? '+' : ''}${fmt(c.correction)}</td>
        <td>${fmt(c.back_delta)}</td>
        <td>${c.within_limit ? '≤' : '＞'} ${fmt(draft.observations[k].limit)}</td>
      </tr>`,
    )
    .join('');

  // Fundamental cycles close naturally at 0 because corrections were
  // selected jointly over *all* elevations.
  const stations = draft.stations.map((s, i) => ({
    name: s.name.trim(),
    elevation: result.elevations[i].elevation,
  }));
  const closures = cycleClosures(
    draft.stations.map((s) => ({ name: s.name.trim() })),
    draft.observations,
    stations.map((s) => s.elevation),
  );
  const names = stations.map((s) => s.name);
  if (closures.length === 0) {
    $('loopsBody').innerHTML =
      '<tr><td colspan="2">网络无环（树状网），没有需要核验的环路。</td></tr>';
  } else {
    $('loopsBody').innerHTML = closures
      .map((cy, i) => {
        const path = cy.steps.map(([a, b]) => `${names[a]}→${names[b]}`).join('，');
        return `<tr class="${cy.closure === 0 ? 'closed' : 'over'}">
          <td title="${path}">环 ${i + 1}：${path}</td>
          <td>${fmt(cy.closure)}</td></tr>`;
      })
      .join('');
  }
}

function init() {
  $('benchmarkHeight').addEventListener('input', (ev) => {
    const v = ev.target.value;
    draft.benchmarkHeight = v === '' || v === '-' ? v : Number(v);
    markDirty();
  });
  $('addStation').addEventListener('click', () => {
    if (draft.stations.length >= STATION_LIMIT) return;
    draft.stations.push({ name: `S${draft.stations.length + 1}`, benchmark: false });
    renderAll();
    markDirty();
  });
  $('addObservation').addEventListener('click', () => {
    if (draft.observations.length >= OBS_LIMIT) return;
    const first = draft.stations[0]?.name ?? '';
    draft.observations.push({ start: first, end: first, delta: 0, limit: 3 });
    renderObservations();
    markDirty();
  });
  $('submitBtn').addEventListener('click', submit);
  $('resetBtn').addEventListener('click', () => {
    draft = structuredClone(SAMPLE);
    $('benchmarkHeight').value = String(SAMPLE.benchmarkHeight);
    result = null;
    $('resultPanel').hidden = true;
    $('draftHint').hidden = true;
    renderAll();
  });
  renderAll();
}

init();

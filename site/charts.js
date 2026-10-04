// Dependency-free SVG charts. Colors come from CSS custom properties so light and dark share one code path.
const NS = 'http://www.w3.org/2000/svg';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY = 864e5;

export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const ms = d => Date.parse(d + 'T00:00:00Z');
export const fmtDate = t => { const d = new Date(t); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };

function svg(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

function niceTicks(lo, hi, n = 5) {
  const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw)), r = raw / mag;
  const step = (r >= 7.5 ? 10 : r >= 3.5 ? 5 : r >= 1.5 ? 2 : 1) * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
  return out;
}

function logTicks(lo, hi) {
  const out = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
    for (const m of [1, 2, 5]) { const v = m * 10 ** e; if (v >= lo && v <= hi) out.push(v); }
  return out;
}

/**
 * lineChart(el, opts)
 * opts.series: [{label, color, points: [{t, v, tip?}], line?: true, markers?: false, hollow?: p => bool}]
 * opts.ranges: [{t, lo, hi, mid, color, label, tip}]  vertical low-high whiskers with a mid tick
 * opts.fmt: value formatter; opts.log, opts.invert, opts.height
 */
export function lineChart(el, opts) {
  el.classList.add('chart');
  const draw = () => {
    el.innerHTML = '';
    const W = Math.max(el.clientWidth, 280), H = opts.height || 240;
    const m = { l: 46, r: 14, t: 10, b: 24 };
    const fmt = opts.fmt || (v => v.toLocaleString());
    const ranges = opts.ranges || [];
    const pts = opts.series.flatMap(s => s.points);
    const ts = pts.map(p => p.t).concat(ranges.map(r => r.t));
    const vs = pts.map(p => p.v).concat(ranges.flatMap(r => [r.lo, r.hi]));
    if (!ts.length) return;
    const t0 = Math.min(...ts), t1 = Math.max(...ts) + (ranges.length ? 6 * DAY : 0);
    let v0 = opts.log || opts.invert ? Math.min(...vs) : 0, v1 = Math.max(...vs);
    if (opts.log) { v0 *= 0.8; v1 *= 1.25; }
    const yt = opts.log ? logTicks(v0, v1) : niceTicks(v0, v1);
    if (!opts.log) v1 = Math.max(v1, yt[yt.length - 1]);
    const x = t => m.l + (t - t0) / (t1 - t0 || 1) * (W - m.l - m.r);
    const f = opts.log ? Math.log : (v => v);
    const y = v => { const u = (f(v) - f(v0)) / (f(v1) - f(v0) || 1); return m.t + (opts.invert ? u : 1 - u) * (H - m.t - m.b); };

    const root = svg('svg', { viewBox: `0 0 ${W} ${H}`, height: H, role: 'img', 'aria-label': opts.label || '' }, el);
    for (const v of yt) {
      svg('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: 'var(--grid)' }, root);
      svg('text', { x: m.l - 6, y: y(v) + 4, 'text-anchor': 'end' }, root).textContent = fmt(v);
    }
    const d = new Date(t0); d.setUTCDate(1);
    const months = [];
    for (; +d <= t1; d.setUTCMonth(d.getUTCMonth() + 1)) if (+d >= t0) months.push(+d);
    const every = Math.ceil(months.length / Math.max(2, Math.floor((W - m.l - m.r) / 52)));
    months.forEach((t, i) => {
      if (i % every) return;
      const dd = new Date(t), mo = dd.getUTCMonth();
      svg('text', { x: x(t), y: H - 6, 'text-anchor': 'middle' }, root).textContent = MONTHS[mo] + (mo === 0 || i === 0 ? ` ’${String(dd.getUTCFullYear()).slice(2)}` : '');
    });
    svg('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: 'var(--axis)' }, root);

    const cross = svg('line', { y1: m.t, y2: H - m.b, stroke: 'var(--axis)', visibility: 'hidden' }, root);
    for (const s of opts.series) {
      if (s.line !== false && s.points.length > 1)
        svg('path', { d: s.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(''), fill: 'none', stroke: s.color, 'stroke-width': s.width || 2, opacity: s.opacity || 1, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, root);
      if (s.markers) for (const p of s.points) {
        const hollow = s.hollow && s.hollow(p);
        svg('circle', { cx: x(p.t), cy: y(p.v), r: hollow ? 4 : 5, fill: hollow ? 'var(--surface)' : s.color, stroke: hollow ? s.color : 'var(--surface)', 'stroke-width': 2 }, root);
      }
    }
    for (const r of ranges) {
      svg('line', { x1: x(r.t), x2: x(r.t), y1: y(r.lo), y2: y(r.hi), stroke: r.color, 'stroke-width': 2, 'stroke-linecap': 'round' }, root);
      for (const v of [r.lo, r.hi]) svg('line', { x1: x(r.t) - 4, x2: x(r.t) + 4, y1: y(v), y2: y(v), stroke: r.color, 'stroke-width': 2, 'stroke-linecap': 'round' }, root);
      svg('rect', { x: x(r.t) - 5, y: y(r.mid) - 5, width: 10, height: 10, fill: r.color, stroke: 'var(--surface)', 'stroke-width': 2, transform: `rotate(45 ${x(r.t)} ${y(r.mid)})` }, root);
    }
    const dots = opts.series.map(s => svg('circle', { r: 5, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 2, visibility: 'hidden' }, root));

    // Hover: snap to the nearest observed date, then list every series observed on that date.
    const tip = document.createElement('div');
    tip.className = 'tip'; tip.hidden = true; el.appendChild(tip);
    const stops = [...new Set(ts)].sort((a, b) => a - b);
    const hide = () => { tip.hidden = true; cross.setAttribute('visibility', 'hidden'); dots.forEach(c => c.setAttribute('visibility', 'hidden')); };
    const move = e => {
      const box = el.getBoundingClientRect(), px = (e.clientX - box.left) * (W / box.width);
      let best = stops[0];
      for (const t of stops) if (Math.abs(x(t) - px) < Math.abs(x(best) - px)) best = t;
      cross.setAttribute('x1', x(best)); cross.setAttribute('x2', x(best)); cross.setAttribute('visibility', 'visible');
      let html = `<div class="t">${fmtDate(best)}</div>`;
      opts.series.forEach((s, i) => {
        const p = s.points.find(q => q.t === best);
        dots[i].setAttribute('visibility', p ? 'visible' : 'hidden');
        if (!p) return;
        dots[i].setAttribute('cx', x(p.t)); dots[i].setAttribute('cy', y(p.v));
        html += `<div class="r"><span class="sw" style="background:${s.color}"></span>${esc(s.label)}<b>${esc(p.text || fmt(p.v))}</b></div>` + (p.tip ? `<div class="n">${esc(p.tip)}</div>` : '');
      });
      for (const r of ranges) if (r.t === best)
        html += `<div class="r"><span class="sw" style="background:${r.color};border-radius:0"></span>${esc(r.label)}<b>${fmt(r.mid)}</b></div><div class="n">${esc(r.tip)}</div>`;
      tip.innerHTML = html; tip.hidden = false;
      const left = x(best) * (box.width / W);
      tip.style.top = '8px';
      tip.style.left = left > box.width / 2 ? '' : `${left + 12}px`;
      tip.style.right = left > box.width / 2 ? `${box.width - left + 12}px` : '';
    };
    root.addEventListener('pointermove', move);
    root.addEventListener('pointerdown', move);
    root.addEventListener('pointerleave', hide);
  };
  draw();
  let w = el.clientWidth;
  new ResizeObserver(() => { if (el.clientWidth !== w) { w = el.clientWidth; draw(); } }).observe(el);
}

/** Three-column node graph: sources -> revenue segments -> company run rate. */
export function nodeGraph(el, { sources, segments, companies }) {
  el.classList.add('graph');
  const rowH = 30, gap = 8, top = 28, W = 900, nodeW = [270, 270, 150], colX = [0, 340, 750];
  const H = top + sources.length * (rowH + gap);
  const root = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'How public data sources connect to revenue segments and company run rate' }, el);
  ['Public sources', 'Revenue segments', 'Annualized run rate'].forEach((t, i) => { const h = svg('text', { x: colX[i], y: 14, class: 'colhead' }, root); h.textContent = t; });
  const place = (items, col) => {
    const total = items.length * (rowH + gap), off = top + (H - top - total) / 2;
    return Object.fromEntries(items.map((it, i) => [it.id, { ...it, col, x: colX[col], y: off + i * (rowH + gap), w: nodeW[col] }]));
  };
  const nodes = { ...place(sources, 0), ...place(segments, 1), ...place(companies, 2) };
  const edges = [];
  for (const s of sources) for (const g of s.informs) edges.push([s.id, g]);
  for (const c of companies) for (const g of c.segments) edges.push([g, c.id]);
  const edgeLayer = svg('g', {}, root);
  const paths = edges.map(([a, b]) => {
    const A = nodes[a], B = nodes[b], x1 = A.x + A.w, y1 = A.y + rowH / 2, x2 = B.x, y2 = B.y + rowH / 2, mx = (x1 + x2) / 2;
    return { a, b, el: svg('path', { d: `M${x1},${y1}C${mx},${y1} ${mx},${y2} ${x2},${y2}` }, edgeLayer) };
  });
  const groups = {};
  const focus = id => {
    // Follow links in the direction of the flow on both sides of the focused node.
    const on = new Set(id ? [id] : []);
    if (id) {
      let grew = true;
      const down = new Set([id]), up = new Set([id]);
      while (grew) { grew = false; for (const p of paths) { if (down.has(p.a) && !down.has(p.b)) { down.add(p.b); grew = true; } if (up.has(p.b) && !up.has(p.a)) { up.add(p.a); grew = true; } } }
      down.forEach(n => on.add(n)); up.forEach(n => on.add(n));
      for (const p of paths) { const hot = (down.has(p.a) && down.has(p.b)) || (up.has(p.a) && up.has(p.b)); p.el.classList.toggle('hot', hot); p.el.classList.toggle('dim', !hot); }
    } else for (const p of paths) p.el.classList.remove('hot', 'dim');
    for (const k in groups) { groups[k].classList.toggle('dim', !!id && !on.has(k)); groups[k].classList.toggle('hot', k === id); }
  };
  for (const n of Object.values(nodes)) {
    const g = svg('g', { tabindex: 0, class: n.status === 'planned' ? 'planned' : '' }, root);
    svg('rect', { class: 'node', x: n.x + .5, y: n.y + .5, width: n.w - 1, height: rowH - 1, rx: 6 }, g);
    if (n.color) svg('circle', { cx: n.x + 14, cy: n.y + rowH / 2, r: 5, fill: n.color }, g);
    svg('text', { x: n.x + (n.color ? 26 : 10), y: n.y + rowH / 2 + 4 }, g).textContent = n.name + (n.status === 'planned' ? ' (planned)' : '');
    g.addEventListener('pointerenter', () => focus(n.id));
    g.addEventListener('focus', () => focus(n.id));
    g.addEventListener('pointerleave', () => focus(null));
    g.addEventListener('blur', () => focus(null));
    groups[n.id] = g;
  }
}

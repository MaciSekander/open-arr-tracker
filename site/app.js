import { lineChart, nodeGraph, esc, ms, fmtDate } from './charts.js';

const COLOR = { OpenAI: 'var(--series-1)', Anthropic: 'var(--series-2)' };
const CASES = ['low', 'reference', 'high'];
const CASE_NAME = { low: 'Low', reference: 'Reference', high: 'High' };
const $ = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content; };
const usd = (v, d = 1) => `$${v.toFixed(d)}B`;
const pct = (v, d = 1) => `${v.toFixed(d)}%`;
const signed = (v, f) => `${v >= 0 ? '+' : '−'}${f(Math.abs(v))}`;
const compact = v => v >= 1e6 ? `${+(v / 1e6).toPrecision(3)}M` : v >= 1e3 ? `${+(v / 1e3).toPrecision(3)}K` : `${+v.toPrecision(3)}`;
const qual = a => (a.qualifier === '=' ? '' : a.qualifier) + usd(a.value_b, a.value_b % 1 ? 1 : 0);
const sw = c => `<span class="sw" style="background:${COLOR[c]}"></span>`;
const legend = items => `<div class="legend">${items.map(([label, color, extra]) => `<span><i style="border-color:${color};${extra || ''}"></i>${esc(label)}</span>`).join('')}</div>`;

let D;
const main = document.getElementById('main');
const anchor = id => D.anchors.find(a => a.id === id);
const totals = co => D.anchors.filter(a => a.company === co && a.kind === 'total_run_rate').sort((a, b) => ms(a.obs_date) - ms(b.obs_date));
const M = co => D.model.companies[co];
const EVID = { filing: ['From a filing', 'live'], reports: ['From reports', 'live'], none: ['No disclosure', 'planned'] };
const evid = r => r.evidence ? `<span class="badge ${EVID[r.evidence][1]}">${EVID[r.evidence][0]}</span>` : '';
const fc = f => `${f.high_b == null ? `more than ${usd(f.low_b, 0)}` : f.low_b === f.high_b ? usd(f.low_b, 0) : `${usd(f.low_b, 0)} to ${usd(f.high_b, 0)}`}`;
const proper = t => t.replace(/\b(api|azure|amazon|google|microsoft)\b/g, w => w === 'api' ? 'API' : w[0].toUpperCase() + w.slice(1));

/* ---------- Overview ---------- */
const rq = l => `${l.qualifier === '=' ? '' : l.qualifier}${usd(l.value_b, 0)}`;
function splitBar(co) {
  const m = M(co), t = m.nowcast.reference, w = v => `${v / t * 100}%`;
  return `<div class="split" role="img" aria-label="${co}: publicly traceable ${usd(m.public.reference)}, residual ${usd(m.residual.reference)}">
      <div class="split-bar"><div style="width:${w(m.public.reference)};background:${COLOR[co]}" title="Part 1 ${usd(m.public.reference)}"></div><div class="assumed" style="width:${w(m.residual.reference)}" title="Part 2 ${usd(m.residual.reference)}"></div></div>
    </div>
    <div class="legend"><span><span class="sw" style="background:${COLOR[co]};border-radius:2px"></span>Part 1 · publicly traceable</span><span><span class="sw assumed-sw"></span>Part 2 · ${esc(proper(M(co).rows.find(r => r.part === 'residual').label.toLowerCase()))}</span></div>`;
}
function overview() {
  const cards = D.meta.companies.map(co => {
    const m = M(co), l = m.latest, t = m.nowcast.reference, res = m.rows.find(r => r.part === 'residual'), fitted = m.fit.methods.find(x => x.is_model);
    const how = m.rolled_forward
      ? `Latest report ${rq(l)} on ${fmtDate(ms(l.obs_date))}, moved forward ${Math.round((ms(m.as_of) - ms(l.obs_date)) / 864e5)} days with ${m.signals.length} signals (${usd(m.nowcast.low, 0)} to ${usd(m.nowcast.high, 0)}).`
      : `Latest report ${rq(l)} on ${fmtDate(ms(l.obs_date))}. No newer signal data yet.`;
    return `<div class="card">
      <div class="co-head">${sw(co)}${co}</div>
      <div class="tile"><div class="label">Annualized run rate, ${fmtDate(ms(m.as_of))}</div><div class="value hero">${usd(m.nowcast.reference)}</div>
        <div class="sub">${how}<br>Typical miss of this method: ${pct(fitted.mape, 0)}, over ${fitted.n} past reports.</div></div>
      ${splitBar(co)}
      <div class="tiles" style="margin-top:12px">
        <div class="tile"><div class="label">Part 1 · Publicly traceable</div><div class="value">${pct(m.public.reference / t * 100, 0)} <span class="unit">of run rate</span></div>
          <div class="sub">${usd(m.public.reference)} of ${usd(t)}; disclosures bound it to ${usd(m.public.low)} to ${usd(m.public.high)}<br>${m.rows.filter(r => r.part === 'public').map(r => proper(r.name.toLowerCase())).join(', ')}</div></div>
        <div class="tile"><div class="label">Part 2 · ${esc(res.label)}</div><div class="value">${pct(m.residual.reference / t * 100, 0)} <span class="unit">of run rate</span></div>
          <div class="sub">${usd(m.residual.reference)} of ${usd(t)}; the remainder, ${usd(m.residual.low)} to ${usd(m.residual.high)}<br>Not visible in any public data</div></div>
      </div>
      ${res.fee_rate ? `<div class="callout">Partners kept about ${pct(res.fee_rate * 100, 0)} of sales made through them in 2025. If that rate still holds, roughly ${usd(m.residual.reference * res.fee_rate, 0)} of the ${usd(m.residual.reference)} is paid on to them as fees.</div>` : ''}
    </div>`;
  }).join('');
  const target = fmtDate(ms(M('OpenAI').outlook.target));
  const outlook = D.meta.companies.map(co => {
    const o = M(co).outlook, pub = D.forecasts.filter(f => f.company === co);
    return `<tr><td>${sw(co)} ${co}</td><td class="num">${usd(o.flat_b, 0)}</td><td class="num">${usd(o.steady_b, 0)}</td><td class="num">${usd(o.added_per_month_b)}</td>
      <td>${pub.length ? pub.map(f => `${fc(f)} <span class="small">(<a href="${esc(f.url)}" rel="noopener">${f.id}</a>, grade ${f.grade})</span>`).join('<br>') : '<span class="muted">None found for year-end run rate</span>'}</td></tr>`;
  }).join('');
  const takeaways = D.meta.companies.map(co => {
    const m = M(co), res = m.rows.find(r => r.part === 'residual'), weak = m.rows.filter(r => r.evidence === 'none');
    return `<li><strong>${co}:</strong> about ${usd(m.nowcast.reference, 0)} a year at the current pace. Roughly ${pct(m.public.reference / m.nowcast.reference * 100, 0)} is publicly traceable; the rest is ${esc(proper(res.name.toLowerCase()))}. ${weak.length ? `The split is loosely bounded because its ${weak.map(r => proper(r.name.toLowerCase())).join(' and ')} revenue has never been disclosed.` : 'The split rests on figures reported from its IPO filing.'}</li>`;
  }).join('');

  main.replaceChildren($(`
    <h1>OpenAI and Anthropic revenue, from public data</h1>
    <p class="lede">Each lab's annualized run rate starts from its latest reported figure and moves with open usage signals. It is then split in two: the part that leaves public traces, and the enterprise and cloud revenue that no public source can see.</p>
    <div class="grid2">${cards}</div>
    <p class="note">Run rate is the latest month's revenue multiplied to a year, not revenue earned in a year. Both parts are shares of that one total; Part 2 is simply what remains after Part 1.</p>
    <h2>In short</h2>
    <ul class="plain">${takeaways}</ul>
    <h2>Run rate through 2026</h2>
    <div class="card">
      <div class="chart-sub">Annualized revenue run rate, USD billions.</div>
      ${legend([['OpenAI', COLOR.OpenAI], ['Anthropic', COLOR.Anthropic], ['Dots: reported (hollow = secondary source)', 'var(--muted)', 'border-top-style:dotted'], ['Thin line: signal-implied between reports', 'var(--muted)', 'border-top-width:1px'], [`Whisker: outlook for ${target}`, 'var(--muted)']])}
      <div id="c-anchors"></div>
      <p class="note">The thin line follows the signals between reports, so the jump at each dot is that period's miss. Hover for detail.</p>
    </div>
    <h2>Outlook for ${target}</h2>
    <p>Two cases you can check by hand: growth stops, or the lab keeps adding what it averaged per month in 2026.</p>
    <div class="card tablewrap"><table>
      <thead><tr><th>Company</th><th class="num">If growth stops</th><th class="num">If the 2026 average continues</th><th class="num">Average added per month</th><th>Published expectation</th></tr></thead>
      <tbody>${outlook}</tbody></table>
      <p class="note">Arithmetic, not a forecast. Published expectations are shown for comparison and never used in the calculation.</p></div>`));

  lineChart(document.getElementById('c-anchors'), {
    height: 360, fmt: v => `$${v}B`, label: 'Annualized run rate: reported, signal-implied and outlook',
    series: D.meta.companies.flatMap(co => [
      { label: `${co} signal-implied`, color: COLOR[co], width: 1, opacity: .55, points: M(co).curve.map(([d, v]) => ({ t: ms(d), v, text: usd(v) })) },
      { label: `${co} reported`, color: COLOR[co], markers: true, hollow: p => p.grade === 'C', line: false,
        points: totals(co).map(a => ({ t: ms(a.obs_date), v: a.value_b, text: qual(a), grade: a.grade, tip: `${a.id} · grade ${a.grade} · ${a.obs_label}. ${a.source}.` })) },
    ]),
    ranges: D.meta.companies.map((co, i) => {
      const o = M(co).outlook;
      return { t: ms(o.target) - i * 5 * 864e5, lo: o.flat_b, hi: o.steady_b, mid: (o.flat_b + o.steady_b) / 2, color: COLOR[co], label: `${co} outlook, midpoint`, tip: `Growth stops: ${usd(o.flat_b, 0)}. 2026 average continues: ${usd(o.steady_b, 0)}.` };
    }),
  });
}

/* ---------- Signals ---------- */
let indexed = false;
function signals() {
  const snapName = { homebrew: 'Homebrew cask installs', open_vsx: 'Open VSX downloads', github: 'GitHub stars', apple_top_free: 'App Store top free rank', openrouter: 'OpenRouter, past week', apple_ratings: 'App Store ratings' };
  const metric = s => s.metric.replace('installs_', 'last ').replace('30d', '30 days').replace('90d', '90 days').replace('365d', '365 days').replace('downloads_cumulative', 'all time').replace('stars_cumulative', 'all time').replace('rank_top100', 'rank today').replace('ratings_cumulative', 'all time').replace('token_share_week_pct', 'share of top-20 tokens, %').replace('tokens_week', 'tokens');
  main.replaceChildren($(`
    <h1>Public signals</h1>
    <p class="lede">Open usage data, cleaned and averaged over 28 days. None of it is revenue; each chart says what it can miss.</p>
    <div class="controls"><span class="small">Scale</span>
      <div class="seg" role="group" aria-label="Scale">
        <button aria-pressed="${!indexed}" data-i="0">Actual values</button><button aria-pressed="${indexed}" data-i="1">Indexed, start = 100</button>
      </div></div>
    ${[['Used in the estimates', s => s.in_model.length], ['Shown for context', s => !s.in_model.length]].map(([title, keep]) => `<h2>${title}</h2>
    <div class="grid2">${D.signals.filter(keep).map(s => {
      const src = D.sources.find(x => x.id === s.source);
      return `<div class="card"><h3>${esc(s.title)}</h3>
        <div class="chart-sub">${esc(indexed && !s.no_index ? 'Index, first observation = 100' : s.unit)} · ${esc(s.subtitle)}${s.in_model.length === 1 ? ` · used for ${s.in_model[0]} only` : ''}</div>
        ${legend(s.series.map(x => [x.label, COLOR[x.company]]))}
        <div id="c-${s.id}"></div>
        <p class="note">${esc(s.note)} Source: <a href="${esc(src.url)}" rel="noopener">${esc(src.name)}</a>.</p></div>`;
    }).join('')}</div>`).join('')}
    <h2>Cloud partners and gateways</h2>
    <p>The closest public view of the part no signal can see. Quarterly and coarse: none of these separates out OpenAI or Anthropic revenue.</p>
    <div class="card tablewrap"><table>
      <thead><tr><th>Company</th><th>Measure</th><th>Period</th><th class="num">Value</th><th class="num">Growth</th><th>Note</th></tr></thead>
      <tbody>${D.published.cloud.map(c => `<tr><td><a href="${esc(c.url)}" rel="noopener">${esc(c.company)}</a></td><td>${esc(c.metric)}</td><td>${esc(c.period)}</td><td class="num">${esc(c.value)}</td><td class="num">${esc(c.growth)}</td><td class="small">${esc(c.note)}</td></tr>`).join('')}</tbody></table>
      <p class="note">From each company's own earnings release.</p></div>
    <details><summary>Vercel AI Gateway index (${D.published.vercel.length})</summary>
    <div class="card tablewrap"><table>
      <thead><tr><th>Month</th><th>Measure</th><th class="num">Value</th><th>Published</th></tr></thead>
      <tbody>${D.published.vercel.map(c => `<tr><td>${new Date(c.month + '-01T00:00:00Z').toLocaleString('en', { month: 'short', year: 'numeric', timeZone: 'UTC' })}</td><td>${esc(c.metric)}</td><td class="num">${esc(c.value)}</td><td><a href="${esc(c.url)}" rel="noopener">${fmtDate(ms(c.pub_date))}</a></td></tr>`).join('')}</tbody></table>
      <p class="note">One gateway's traffic, with spend valued at list prices. It shows mix, not company revenue.</p></div></details>
    <details><summary>Point-in-time snapshots (${D.snapshots.filter(s => s.value !== '').length})</summary>
    <div class="card tablewrap"><table>
      <thead><tr><th>Source</th><th>Item</th><th>Measure</th><th class="num">Value</th></tr></thead>
      <tbody>${D.snapshots.filter(s => s.value !== '').map(s => `<tr><td>${esc(snapName[s.source] || s.source)}</td><td>${esc(s.item)}</td><td>${esc(metric(s))}</td><td class="num">${s.metric.startsWith('rank') ? '#' : ''}${(+s.value).toLocaleString()}</td></tr>`).join('')}</tbody></table>
      <p class="note">Collected ${fmtDate(ms(D.meta.vintage))}. These sources publish no history, so trends appear only as weekly collections accumulate. Not used in any estimate yet.</p></div></details>
    `));
  main.querySelectorAll('.seg button').forEach(b => b.onclick = () => { indexed = b.dataset.i === '1'; signals(); });
  for (const s of D.signals) {
    const idx = indexed && !s.no_index;
    lineChart(document.getElementById(`c-${s.id}`), {
      log: s.log, invert: s.invert, label: s.title,
      fmt: idx ? v => `${Math.round(v)}` : s.invert ? v => `#${v.toLocaleString()}` : compact,
      series: s.series.map(x => ({ label: x.label, color: COLOR[x.company], points: x.points.map(([d, v]) => ({ t: ms(d), v: idx ? v / x.points[0][1] * 100 : v })) })),
    });
  }
}

/* ---------- Model ---------- */
const state = {};
function reset(co) {
  const m = M(co), r = id => m.rows.find(x => x.segment === id);
  state[co] = { total: +m.nowcast.reference.toFixed(1), consumer: +r('consumer').est.reference.toFixed(1), advertising: r('advertising') ? +r('advertising').est.reference.toFixed(2) : null,
    apiOfBusiness: !!r('direct_api').of_business, api: r('direct_api').of_business ? (r('direct_api').of_business.low + r('direct_api').of_business.high) / 2 * 100 : +r('direct_api').est.reference.toFixed(1), perMonth: +m.outlook.added_per_month_b.toFixed(2), custom: false };
}
function builder(co) {
  const s = state[co], m = M(co), r = id => m.rows.find(x => x.segment === id);
  const ads = s.advertising || 0, business = s.total - s.consumer - ads, api = s.apiOfBusiness ? business * s.api / 100 : s.api, pub = s.consumer + ads + api, rest = s.total - pub;
  const yearEnd = s.total + s.perMonth * m.outlook.months;
  const cite = row => row.cites.length ? ` Cites ${row.cites.join(', ')}.` : '';
  const band = row => `${usd(row.est.low)} to ${usd(row.est.high)}`;
  const line = (row, input, value) => `<tr><td>${esc(row.name)}<br>${evid(row)}</td><td class="num">${input}</td><td class="num">${usd(value)}</td><td class="num">${pct(value / s.total * 100, 0)}</td></tr>
    <tr class="detail"><td colspan="4">Bounds: ${row.of_business ? `${pct(row.of_business.low * 100, 0)} to ${pct(row.of_business.high * 100, 0)} of business revenue` : band(row)}</td></tr>`;
  const num = (k, v, step, label) => `<input type="number" data-k="${k}" value="${v}" step="${step}" min="0" aria-label="${label}">`;
  return `<div class="card" data-co="${co}">
    <div class="chart-head"><div class="co-head" style="margin:0">${sw(co)}${co}</div><div class="seg"><button data-reset aria-pressed="${!s.custom}">${s.custom ? 'Reset to defaults' : 'Defaults'}</button></div></div>
    <p class="small" style="margin:8px 0">Total run rate ${num('total', s.total, 1, 'Total run rate, USD billions')} $B · default is the ${fmtDate(ms(m.as_of))} nowcast</p>
    <div class="tablewrap"><table>
      <thead><tr><th>Segment</th><th class="num">Your input</th><th class="num">Run rate</th><th class="num">Share</th></tr></thead>
      <tbody><tr class="part"><td colspan="4">Part 1 · Publicly traceable</td></tr>
        ${line(r('consumer'), `${num('consumer', s.consumer, 0.5, 'Subscriptions, USD billions')} $B`, s.consumer)}
        ${r('advertising') ? line(r('advertising'), `${num('advertising', s.advertising, 0.25, 'Advertising, USD billions')} $B`, ads) : ''}
        ${line(r('direct_api'), s.apiOfBusiness ? `${num('api', s.api, 5, 'Direct API share of business revenue, percent')} % of business` : `${num('api', s.api, 0.5, 'Direct API, USD billions')} $B`, api)}
        <tr class="sub"><td>Part 1 subtotal</td><td></td><td class="num">${usd(pub)}</td><td class="num">${pct(pub / s.total * 100, 0)}</td></tr>
        <tr class="part"><td colspan="4">Part 2 · ${esc(r('enterprise_cloud').label)} (the remainder)</td></tr>
        <tr><td>${esc(r('enterprise_cloud').name)}</td><td class="num small">residual</td><td class="num">${usd(rest)}</td><td class="num">${pct(rest / s.total * 100, 0)}</td></tr>
        <tr class="total"><td>Total</td><td></td><td class="num">${usd(s.total)}</td><td class="num">100%</td></tr>
      </tbody></table></div>
    ${rest < 0 ? '<p class="warn">Part 1 exceeds the total. Lower an input.</p>' : ''}
    <details class="inline"><summary>Why these bounds</summary><ul>${m.rows.map(row => `<li><strong>${esc(row.name)}.</strong> ${esc(row.basis)}${cite(row)}</li>`).join('')}${m.two_piece ? `<li><strong>Two pieces.</strong> ${esc(m.two_piece.basis)} Cites ${m.two_piece.cites.join(', ')}.</li>` : ''}</ul></details>
    <p class="small" style="margin-top:16px">If it adds ${num('perMonth', s.perMonth, 0.5, 'Run rate added per month, USD billions')} $B a month, run rate reaches <strong>${usd(yearEnd, 0)}</strong> on ${fmtDate(ms(m.outlook.target))}. Default is its 2026 average.</p>
  </div>`;
}
function model() {
  for (const co of D.meta.companies) if (!state[co]) reset(co);
  const methods = D.meta.companies.map(co => M(co).fit.methods.map((x, i) => `<tr${x.is_model ? ' class="model"' : ''}>${i ? '' : `<td rowspan="${M(co).fit.methods.length}">${sw(co)} ${co}</td>`}<td>${esc(x.method)}${x.is_model ? ' (used)' : ''}</td><td class="num">${x.n}</td><td class="num">${pct(x.mape, 0)}</td><td class="num">${signed(x.bias_pct, v => pct(v, 0))}</td></tr>`).join('')).join('');
  const pairs = D.meta.companies.map(co => M(co).fit.pairs.map(p => { const pr = p.model_b; return `<tr><td>${sw(co)} ${co}</td><td>${fmtDate(ms(p.date))}</td><td class="num">${signed((p.signal_ratio - 1) * 100, v => pct(v, 0))}</td><td class="num">${signed((p.actual_b / p.prev_b - 1) * 100, v => pct(v, 0))}</td><td class="num">${pr == null ? '<span class="muted">n/a</span>' : usd(pr)}</td><td class="num">${usd(p.actual_b, 0)}</td><td class="num">${pr == null ? '' : signed((pr / p.actual_b - 1) * 100, v => pct(v, 0))}</td></tr>`; }).join('')).join('');
  const per = D.per_signal.map(p => `<tr><td>${sw(p.company)} ${p.company}</td><td>${esc(p.signal)}</td><td>${p.in_model ? 'Used' : '<span class="muted">Context</span>'}</td><td class="num">${p.n}</td><td class="num">${pct(p.mape, 0)}</td><td class="num">${signed(p.bias_pct, v => pct(v, 0))}</td></tr>`).join('');
  const a = M('Anthropic'), o = M('OpenAI'), used = m => m.fit.methods.find(x => x.is_model), by = (m, k) => m.fit.methods.find(x => x.method.startsWith(k));

  main.replaceChildren($(`
    <h1>How the numbers are built</h1>
    <p class="lede">No hand-set growth rates. The total follows reports and signals, the split follows what each company has disclosed, and everything else is the remainder.</p>
    <div class="steps">
      <div class="step"><b>1 · Total</b><span>Take the latest reported run rate and move it by the median growth of the signals since that report.</span></div>
      <div class="step"><b>2 · Part 1</b><span>Size subscriptions, advertising and direct API from cited disclosures. The default is the midpoint of each bound.</span></div>
      <div class="step"><b>3 · Part 2</b><span>Whatever remains: revenue through channels public data cannot see.</span></div>
    </div>
    <h2>Try your own inputs</h2>
    <div class="grid2 wide" id="builders">${D.meta.companies.map(builder).join('')}</div>

    <h2>How accurate has it been?</h2>
    <p>Each past report is predicted from the one before it, then compared with what was actually reported.</p>
    <ul class="plain">
      <li><strong>Anthropic: ${pct(used(a).mape, 0)} typical miss</strong> over ${used(a).n} reports, against ${pct(by(a, 'Prior trend').mape, 0)} for a trend line and ${pct(by(a, 'Carry').mape, 0)} for assuming no change. Run rate has moved almost one for one with developer activity (elasticity ${a.elasticity.toFixed(2)}).</li>
      <li><strong>OpenAI: ${pct(used(o).mape, 0)} typical miss</strong> over ${used(o).n} reports, against ${pct(by(o, 'Signals, fitted').mape, 0)} when it is treated as one business. It is modelled in two pieces: business revenue (${pct(o.two_piece.business_share * 100, 0)} of the total) moves with developer signals including Codex, and consumer revenue is held at its last reported level. It still fell well short of the September report, when consumer revenue also jumped and no public signal showed it.</li>
    </ul>
    <div class="card tablewrap"><table>
      <thead><tr><th>Company</th><th>Report date</th><th class="num">Signals grew</th><th class="num">Reported grew</th><th class="num">Model said</th><th class="num">Reported</th><th class="num">Miss</th></tr></thead>
      <tbody>${pairs}</tbody></table>
      <p class="note">Each row predicts one report from the report before it. "n/a" means the business share was not disclosed at the starting report, so the two-piece method could not run.</p></div>
    <h2>Is that better than guessing?</h2>
    <p>The same test with two simple alternatives. Shorter bars are better.</p>
    <div class="grid2">${D.meta.companies.map(co => { const rows = [['This model', used(M(co)), true], ['Extend the previous trend', by(M(co), 'Prior trend')], ['Assume no change', by(M(co), 'Carry')]]; return `<div class="card"><div class="co-head">${sw(co)}${co}</div>
      ${rows.map(([name, x, mine]) => `<div class="cmp"><span>${name}</span><div class="cmp-track"><div style="width:${Math.min(100, x.mape / 40 * 100)}%;background:${mine ? COLOR[co] : 'var(--axis)'}"></div></div><b>${pct(x.mape, 0)}</b></div>`).join('')}
      <p class="note">Average miss over ${used(M(co)).n} reports for this model.</p></div>`; }).join('')}</div>
    <details><summary>All methods, with bias</summary>
    <div class="card tablewrap"><table>
      <thead><tr><th>Company</th><th>Method</th><th class="num">Reports predicted</th><th class="num">Typical miss</th><th class="num">Bias</th></tr></thead>
      <tbody>${methods}</tbody></table>
      <p class="note">Typical miss is the average size of the error. Bias keeps the direction: negative means the method ran too low on average. Small samples, and history is each source's latest published data, so this is a diagnostic, not a live track record.</p></div></details>
    <details><summary>Each signal on its own</summary>
    <div class="card tablewrap"><table>
      <thead><tr><th>Company</th><th>Signal</th><th>Role</th><th class="num">Reports</th><th class="num">Typical miss</th><th class="num">Bias</th></tr></thead>
      <tbody>${per}</tbody></table>
      <p class="note">Each signal scaled one for one against every report. A series is never measured across a known counting break.</p></div></details>`));

  const wire = () => main.querySelectorAll('#builders [data-co]').forEach(card => {
    const co = card.dataset.co;
    card.querySelector('[data-reset]').onclick = () => { reset(co); redraw(co); };
    card.querySelectorAll('input').forEach(inp => inp.onchange = () => { state[co][inp.dataset.k] = Math.max(0, parseFloat(inp.value) || 0); state[co].custom = true; redraw(co); });
  });
  const redraw = co => { main.querySelector(`#builders [data-co="${co}"]`).replaceWith($(builder(co))); wire(); };
  wire();
}

/* ---------- Sources ---------- */
function sources() {
  const live = D.sources.filter(s => s.status === 'live'), planned = D.sources.filter(s => s.status === 'planned');
  const anchorRows = D.anchors.slice().sort((a, b) => a.company.localeCompare(b.company) || ms(a.obs_date) - ms(b.obs_date)).map(a => `<tr>
    <td>${a.id}</td><td>${sw(a.company)} ${a.company}</td><td>${esc(a.kind.replaceAll('_', ' '))}</td><td class="num">${qual(a)}</td><td>${esc(a.obs_label)}</td>
    <td><span class="badge" title="${esc(D.grades[a.grade])}">${a.grade}</span></td>
    <td><a href="${esc(a.url)}" rel="noopener">${esc(a.source)}</a>${a.excerpt ? `<br><span class="small">“${esc(a.excerpt)}”</span>` : ''}<br><span class="small">${esc(a.note)}</span></td></tr>`).join('');
  main.replaceChildren($(`
    <h1>Sources and how they connect</h1>
    <p class="lede">${live.length} public sources feed this site${planned.length ? `; ${planned.length} more are planned and contribute nothing yet` : ''}.</p>
    <div class="card"><div id="graph"></div>
      <p class="note">Hover or tab to a node to trace what it informs. A link means the source speaks to that segment; it does not mean the segment is measured. Enterprise contracts and cloud resale have almost nothing pointing at them, which is why they are a residual.</p></div>
    <h2>Source catalogue</h2>
    <div class="card tablewrap"><table>
      <thead><tr><th>Source</th><th>Status</th><th>Measures</th><th>Blind spot</th><th>Access and cadence</th></tr></thead>
      <tbody>${D.sources.map(s => `<tr><td>${s.url ? `<a href="${esc(s.url)}" rel="noopener">${esc(s.name)}</a>` : esc(s.name)}</td>
        <td><span class="badge ${s.status}">${s.status === 'live' ? 'Collected' : 'Planned'}</span></td>
        <td>${esc(s.measures)}</td><td>${esc(s.blind_spot)}</td><td>${esc(s.access)}<br><span class="small">${esc(s.cadence)}</span></td></tr>`).join('')}</tbody></table></div>
    <h2>The evidence</h2>
    <p>Grades describe how the claim was read, not whether it is true: ${Object.entries(D.grades).map(([g, t]) => `<strong>${g}</strong> ${esc(t.toLowerCase())}`).join('; ')}.</p>
    <details open><summary>Reported run rates and revenue (${D.anchors.length})</summary>
    <div class="card tablewrap"><table>
      <thead><tr><th>ID</th><th>Company</th><th>Metric</th><th class="num">Value</th><th>Observed</th><th>Grade</th><th>Source, wording and caveat</th></tr></thead>
      <tbody>${anchorRows}</tbody></table></div></details>
    <details><summary>Published expectations (${D.forecasts.length})</summary>
    <div class="card tablewrap"><table>
      <thead><tr><th>ID</th><th>Company</th><th>What</th><th class="num">Value</th><th>Published</th><th>Grade</th><th>Source and caveat</th></tr></thead>
      <tbody>${D.forecasts.map(f => `<tr><td>${f.id}</td><td>${sw(f.company)} ${f.company}</td><td>${esc(f.metric)}</td><td class="num">${fc(f)}</td><td>${f.pub_date ? fmtDate(ms(f.pub_date)) : ''}</td><td><span class="badge" title="${esc(D.grades[f.grade])}">${f.grade}</span></td><td><a href="${esc(f.url)}" rel="noopener">${esc(f.who)}</a>${f.excerpt ? `<br><span class="small">“${esc(f.excerpt)}”</span>` : ''}<br><span class="small">${esc(f.note)}</span></td></tr>`).join('')}</tbody></table>
      <p class="note">Shown for comparison only; never used to fit or adjust any number.</p></div></details>
    <details><summary>Mix and customer disclosures (${D.context.length})</summary>
    <div class="card tablewrap"><table>
      <thead><tr><th>ID</th><th>Company</th><th>Claim</th><th>Date</th><th>Grade</th><th>Use</th></tr></thead>
      <tbody>${D.context.map(c => `<tr><td>${c.id}</td><td>${sw(c.company)} ${c.company}</td><td><a href="${esc(c.url)}" rel="noopener">${esc(c.claim)}</a></td><td>${fmtDate(ms(c.date))}</td><td><span class="badge">${c.grade}</span></td><td>${esc(c.note)}</td></tr>`).join('')}</tbody></table></div></details>`));
  nodeGraph(document.getElementById('graph'), {
    sources: D.sources, segments: D.model.segments.map(s => ({ ...s, name: `${s.name} · ${s.part === 'public' ? 'Part 1' : 'Part 2'}` })),
    companies: D.meta.companies.map(co => ({ id: co, name: co, color: COLOR[co], segments: M(co).rows.map(r => r.segment) })),
  });
}

/* ---------- Method and data ---------- */
function about() {
  const files = ['npm_daily.csv', 'pypi_daily.csv', 'wikipedia_daily.csv', 'ramp_token_daily_7d.csv', 'ramp_adoption_monthly.csv', 'tranco_sampled.csv', 'snapshots.csv', 'manifest.json'];
  main.replaceChildren($(`
    <h1>Method and data</h1>
    <p class="lede">Everything on this site is generated from four registry files and one dated data snapshot. Nothing is hand-edited after the build.</p>
    <h2>Method</h2>
    <ul class="plain">
      <li><strong>Register reports.</strong> One entry per disclosure with its exact wording, observation date, publication date and an evidence grade. Published forecasts are kept separately and never used to fit anything.</li>
      <li><strong>Collect signals.</strong> Raw responses are saved with URL, timestamp and hash, then reduced to the series under Signals.</li>
      <li><strong>Total.</strong> Latest report × (median signal growth since that report) ^ elasticity. Growth compares ${D.model.window_days}-day averages. Elasticity is fitted on Anthropic's consecutive reports. OpenAI has too few reports to fit its own, so its business piece borrows that elasticity and its consumer piece is held at the last reported level.</li>
      <li><strong>Split.</strong> Part 1 segments take the midpoint of bounds set by cited disclosures. Part 2 is the remainder.</li>
      <li><strong>Check.</strong> Every report is predicted from the previous one, out of sample, and all misses are published.</li>
    </ul>
    <h2>Known limits</h2>
    <ul class="plain">
      <li>The split is bounded, not measured. Anthropic's rests on 2025 figures reported from its IPO filing. OpenAI has disclosed far less, so its direct API default is a placeholder.</li>
      <li>Signals measure developer activity. That has tracked Anthropic's run rate closely and OpenAI's poorly.</li>
      <li>The elasticity rests on six Anthropic reports. OpenAI's two-piece model has been tested on only two.</li>
      <li>Reports are unaudited and often thresholds. Anthropic's cloud partners keep a fee on sales made through them, and the two companies may present partner revenue differently, so their totals are not strictly comparable.</li>
      <li>A series with a known counting break is never measured across it.</li>
      <li>Data was collected ${fmtDate(ms(D.meta.vintage))}. Cloud and gateway figures are transcribed by hand from published reports.</li>
    </ul>
    <h2>Terms</h2>
    <ul class="plain">
      <li><strong>Run rate (ARR).</strong> A recent period's revenue scaled to twelve months. A $100B run rate means roughly $8.3B in the latest month, not $100B earned this year.</li>
      <li><strong>Publicly traceable.</strong> Revenue from products whose use shows up in open data: subscriptions, advertising and direct API. Traceable does not mean measured in dollars.</li>
      <li><strong>Residual.</strong> Total minus the traceable part: what enterprise contracts and cloud resale must add up to.</li>
      <li><strong>Elasticity.</strong> How much run rate has moved for each 1% move in the signals. 1.0 means one for one.</li>
      <li><strong>Evidence grade.</strong> How a claim was read: A company statement, B original journalism, C republication, D not verified on a source page.</li>
    </ul>
    <h2>Download</h2>
    <p>Registries: <a href="data/anchors.json">anchors.json</a>, <a href="data/sources.json">sources.json</a>, <a href="data/model.json">model.json</a>, <a href="data/published.json">published.json</a>. Everything the charts use: <a href="data/site.json">site.json</a>.</p>
    <p>Collected files: ${files.map(f => `<a href="data/csv/${f}">${f}</a>`).join(', ')}.</p>
    <h2>Reproduce and contribute</h2>
    <pre>python3 pipeline/collect.py --end YYYY-MM-DD --carry-tranco data/vintage_PREVIOUS
python3 pipeline/build.py
python3 pipeline/serve.py 8000</pre>
    <p>Python standard library only; the site has no build step and no dependencies. To add a source, add an entry to <code>registry/sources.json</code> and a collector step in <code>pipeline/collect.py</code>. To add or correct a disclosure, edit <code>registry/anchors.json</code> with the exact wording and a link.</p>`));
}

const routes = { overview, signals, model, sources, about };
function route() {
  const name = location.hash.slice(1) in routes ? location.hash.slice(1) : 'overview';
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.getAttribute('href') === `#${name}`));
  routes[name]();
  window.scrollTo(0, 0);
}

fetch('data/site.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(d => {
  D = d;
  document.getElementById('vintage').textContent = `Data as of ${fmtDate(ms(D.meta.vintage))}`;
  window.addEventListener('hashchange', route);
  route();
}).catch(e => { main.innerHTML = `<p>Could not load <code>data/site.json</code> (${esc(e.message)}). Run <code>python3 pipeline/build.py</code>, then serve the <code>site</code> folder over HTTP.</p>`; });

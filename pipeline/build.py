"""Build site/data/ from the registries and one data vintage. Standard library only.

    python3 pipeline/build.py [--vintage 2026-10-04]

Everything derived is computed here from the vintage's collected files: signal series,
growth since each starting disclosure, the two-part bridge and the accuracy checks.
"""
import argparse, csv, datetime as dt, json, math, shutil, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ['low', 'reference', 'high']
COMPANIES = ['OpenAI', 'Anthropic']
D = dt.date.fromisoformat


def read(path):
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


# ---------- signal series ----------
# A series is a sorted list of (date, value-or-None). `level(series, day)` is the comparable
# level on a day: a trailing-window mean, so two levels can be divided to get growth.

def trailing_mean(series, day, window, min_share=0.75):
    lo = day - dt.timedelta(days=window - 1)
    obs = [v for d, v in series if lo <= d <= day and v is not None]
    span = [d for d, _ in series if lo <= d <= day]
    return sum(obs) / len(obs) if span and span[0] == lo and len(obs) >= window * min_share else None


def weekly_mean(series, day, window):
    """For series that are already trailing-7-day totals: average disjoint weeks, never overlapping ones."""
    lookup = dict(series)
    vals = [lookup.get(day - dt.timedelta(days=7 * i)) for i in range(window // 7)]
    return sum(vals) / len(vals) if all(v is not None for v in vals) else None


def load_signals(v):
    npm = read(v / 'npm_daily.csv'); pypi = read(v / 'pypi_daily.csv'); wiki = read(v / 'wikipedia_daily.csv')
    ramp = [r for r in read(v / 'ramp_token_daily_7d.csv') if r['token_type'] == 'all_tokens']
    adoption = read(v / 'ramp_adoption_monthly.csv'); tranco = read(v / 'tranco_sampled.csv')

    def npm_s(pkg, skip=None):
        ok = lambda r: r['quality_flag'] == 'observed_positive' and not (skip and skip[0] <= r['date'] <= skip[1])
        return sorted((D(r['date']), int(r['downloads_raw']) if ok(r) else None) for r in npm if r['package'] == pkg)

    def pypi_s(pkg):
        return sorted((D(r['date']), int(r['downloads'])) for r in pypi if r['package'] == pkg)

    def wiki_s(articles):
        days = {}
        for r in wiki:
            if r['article'] in articles:
                days[D(r['date'])] = days.get(D(r['date']), 0) + int(r['views'])
        return sorted(days.items())

    def ramp_s(maker, field, scale):
        return sorted((D(r['usage_date']), float(r[field]) / scale) for r in ramp if r['model_maker'] == maker)

    pair = lambda fn, a, b: {'OpenAI': fn(a), 'Anthropic': fn(b)}
    defs = [
        dict(id='ramp_spend', source='ramp', title='Billed token cost in Ramp sample', unit='USD millions, trailing 7 days', subtitle='Ramp AI Index, all token types', kind='weekly7',
             note='Sample spend, not company revenue. Falls when customers move to cheaper models even if usage rises.',
             labels={c: c for c in COMPANIES}, series={c: ramp_s(c.lower(), 'token_cost_usd_7d', 1e6) for c in COMPANIES}),
        dict(id='ramp_tokens', source='ramp', title='Token volume in Ramp sample', unit='trillion tokens, trailing 7 days', subtitle='Ramp AI Index, all token types', kind='weekly7',
             note='Usage without price. Read beside billed cost: volume can rise while spend falls when customers move to cheaper models.',
             labels={c: c for c in COMPANIES}, series={c: ramp_s(c.lower(), 'token_count_7d', 1e12) for c in COMPANIES}),
        dict(id='npm_sdk', source='npm', title='Official API SDK downloads, JavaScript', unit='downloads per day', subtitle='npm, 28-day average of observed days', kind='daily',
             note='Installs and CI runs, not paid usage. The openai package is also used with other providers.',
             labels={'OpenAI': 'openai', 'Anthropic': '@anthropic-ai/sdk'}, series=pair(npm_s, 'openai', '@anthropic-ai/sdk')),
        dict(id='pypi_sdk', source='pypi', title='Official API SDK downloads, Python', unit='downloads per day', subtitle='PyPI without mirrors, 28-day average', kind='daily',
             note='Public history covers about 180 days only. Both packages step down about 38% in the week of 24 August 2026, which points to a counting change rather than demand, so growth is never measured across that date.',
             breaks=['2026-08-24'],
             labels={'OpenAI': 'openai', 'Anthropic': 'anthropic'}, series=pair(pypi_s, 'openai', 'anthropic')),
        dict(id='npm_aisdk', source='npm', title='Vercel AI SDK provider downloads', unit='downloads per day', subtitle='npm, 28-day average of observed days', kind='daily',
             note='A third-party route to each API that does not depend on the official SDKs. Skews to web developers.',
             labels={'OpenAI': '@ai-sdk/openai', 'Anthropic': '@ai-sdk/anthropic'}, series=pair(npm_s, '@ai-sdk/openai', '@ai-sdk/anthropic')),
        dict(id='npm_coding', source='npm', title='Coding CLI downloads', unit='downloads per day', subtitle='npm, 28-day average of observed days', kind='daily',
             note='Native and Homebrew installs bypass npm. For @openai/codex, 30 April to 11 May 2026 is left out: npm shows an unexplained spike of up to 46M downloads a day.',
             labels={'OpenAI': '@openai/codex', 'Anthropic': '@anthropic-ai/claude-code'},
             series={'OpenAI': npm_s('@openai/codex', ('2026-04-30', '2026-05-11')), 'Anthropic': npm_s('@anthropic-ai/claude-code')}),
        dict(id='wikipedia', source='wikipedia', title='Wikipedia article views', unit='views per day', subtitle='English Wikipedia, human traffic, 28-day average', kind='daily',
             note='Curiosity and news cycles, not product use. The Claude article was renamed in June 2026; both titles are summed.',
             labels={'OpenAI': 'ChatGPT', 'Anthropic': 'Claude'}, series={'OpenAI': wiki_s({'ChatGPT'}), 'Anthropic': wiki_s({'Claude_(language_model)', 'Claude_(AI)'})}),
        dict(id='ramp_adoption', source='ramp', title='Businesses paying each vendor', unit='% of Ramp businesses', subtitle='Ramp AI Index, monthly', kind='raw',
             note='A business paying once is not a seat count or a spend level. Latest month lags by about five weeks.',
             labels={c: c for c in COMPANIES}, series={c: sorted((D(r['date_month']), float(r['adoption_rate_pct'])) for r in adoption if r['vendor'] == c) for c in COMPANIES}),
        dict(id='tranco', source='tranco', title='Consumer domain rank', unit='Tranco rank (1 is most popular)', subtitle='Tranco, sampled month-end and weekly', kind='raw', invert=True, log=True, no_index=True,
             note='Ordinal rank. A change in rank is not a proportional change in traffic, so it drives no growth factor.',
             labels={'OpenAI': 'chatgpt.com', 'Anthropic': 'claude.ai'},
             series={c: sorted((D(r['date']), int(r['rank'])) for r in tranco if r['domain'] == dom and r['quality_flag'] == 'observed') for c, dom in [('OpenAI', 'chatgpt.com'), ('Anthropic', 'claude.ai')]}),
    ]
    return [s for s in defs if all(s['series'][c] for c in COMPANIES)]


def level(sig, company, day, window):
    s = sig['series'][company]
    if sig['kind'] == 'weekly7':
        return weekly_mean(s, day, window)
    if sig['kind'] == 'daily':
        return trailing_mean(s, day, window)
    return None


def growth(sig, company, a, b, window):
    """Level on day b over level on day a, or (None, reason). Refuses to measure across a known break in the series."""
    for brk in sig.get('breaks', []):
        if a - dt.timedelta(days=window) < D(brk) <= b:
            return None, f'series has a measurement break on {brk}'
    x, y = level(sig, company, a, window), level(sig, company, b, window)
    if not x or not y:
        return None, 'no data for the starting window'
    return y / x, None


def latest_day(sig, company):
    return max(d for d, v in sig['series'][company] if v is not None)


def chart_points(sig, company, window):
    s = sig['series'][company]
    if sig['kind'] == 'daily':
        pts = [(d, trailing_mean(s, d, window)) for d, _ in s]
        return [[str(d), round(v)] for d, v in pts if v is not None]
    return [[str(d), round(v, 3)] for d, v in s if v is not None]


# ---------- model ----------

class Model:
    def __init__(self, signals, model, anchors):
        self.cfg, self.win = model, model['window_days']
        self.all_signals = signals
        self.sig = {c: [s for s in signals if s['id'] in model['companies'][c].get('signals', model['nowcast_signals'])] for c in COMPANIES}
        self.hist = {c: sorted((a for a in anchors if a['company'] == c and a['kind'] == 'total_run_rate'), key=lambda a: a['obs_date']) for c in COMPANIES}
        self.fit = {}
        for c in sorted(COMPANIES, key=lambda c: 'two_piece' in model['companies'][c]):  # one-piece companies first; two-piece borrows their elasticity
            self.fit[c] = self._fit(c)

    def ratios(self, company, a, b):
        """Growth of each usable nowcast signal between two days: [(signal, ratio)]."""
        out = []
        for s in self.sig[company]:
            g, _ = growth(s, company, a, b, self.win)
            if g:
                out.append((s, g))
        return out

    def composite(self, company, a, b):
        r = [g for _, g in self.ratios(company, a, b)]
        return statistics.median(r) if len(r) >= self.cfg['min_signals'] else None

    def _pairs(self, company):
        out = []
        h = self.hist[company]
        for i in range(1, len(h)):
            prev, cur = h[i - 1], h[i]
            r = self.composite(company, D(prev['obs_date']), D(cur['obs_date']))
            if not r:
                continue
            trend = None
            if i >= 2:
                older = h[i - 2]
                span = (D(cur['obs_date']) - D(prev['obs_date'])).days / (D(prev['obs_date']) - D(older['obs_date'])).days
                trend = prev['value_b'] * (prev['value_b'] / older['value_b']) ** span
            out.append({'from': prev['id'], 'to': cur['id'], 'date': cur['obs_date'], 'prev_b': prev['value_b'], 'actual_b': cur['value_b'], 'signal_ratio': r,
                        'x': math.log(r), 'y': math.log(cur['value_b'] / prev['value_b']), 'trend_b': trend})
        return out

    @staticmethod
    def _beta(pairs):
        sxx = sum(p['x'] ** 2 for p in pairs)
        return sum(p['x'] * p['y'] for p in pairs) / sxx if sxx else 1.0

    def two_piece(self, company):
        tp = self.cfg['companies'][company].get('two_piece')
        if not tp:
            return None
        donor = next(c for c in COMPANIES if 'two_piece' not in self.cfg['companies'][c])
        return {'share': tp['business_share'], 'beta': self.fit[donor]['elasticity'], 'donor': donor}

    def roll(self, company, base, ratio, beta):
        """Run rate implied by a signal ratio since report `base`. Two-piece: only the business share moves."""
        tp = self.two_piece(company)
        if tp and base['id'] in tp['share']:
            b = base['value_b'] * tp['share'][base['id']]
            return base['value_b'] - b + b * ratio ** tp['beta']
        return base['value_b'] * ratio ** beta

    def _fit(self, company):
        pairs = self._pairs(company)
        beta = self._beta(pairs)
        tp, by_id = self.two_piece(company), {a['id']: a for a in self.hist[company]}
        for i, p in enumerate(pairs):
            rest = pairs[:i] + pairs[i + 1:]
            p['loo_beta'] = self._beta(rest) if rest else None
            p['pred'] = {'Carry forward': p['prev_b'], 'Prior trend': p['trend_b'], 'Signals, one for one': p['prev_b'] * p['signal_ratio'],
                         'Signals, fitted': p['prev_b'] * p['signal_ratio'] ** p['loo_beta'] if p['loo_beta'] is not None else None}
            if tp:
                p['pred']['Two pieces'] = self.roll(company, by_id[p['from']], p['signal_ratio'], beta) if p['from'] in tp['share'] else None
            p['model_b'] = p['pred']['Two pieces' if tp else 'Signals, fitted']
        names = ['Carry forward', 'Prior trend', 'Signals, one for one', 'Signals, fitted'] + (['Two pieces'] if tp else [])
        methods = []
        for name in names:
            rows = [p for p in pairs if p['pred'][name] is not None]
            if rows:
                err = [(p['pred'][name] / p['actual_b'] - 1) * 100 for p in rows]
                methods.append({'method': name, 'n': len(rows), 'mape': statistics.mean(abs(e) for e in err), 'bias_pct': statistics.mean(err), 'is_model': name == ('Two pieces' if tp else 'Signals, fitted')})
        return {'elasticity': tp['beta'] if tp else beta, 'own_elasticity': beta, 'pairs': pairs, 'methods': methods}

    def bounds(self, spec, total):
        v = lambda x: x['b'] if 'b' in x else x['share'] * total
        lo, hi = v(spec['low']), v(spec['high'])
        return {'low': lo, 'reference': (lo + hi) / 2, 'high': hi}

    def company(self, company):
        cfg, h, fit = self.cfg['companies'][company], self.hist[company], self.fit[company]
        latest, d0 = h[-1], D(h[-1]['obs_date'])
        end = min([latest_day(s, company) for s in self.sig[company]] or [d0])
        beta, used, tp = fit['own_elasticity'], [], self.two_piece(company)
        if end > d0:
            used = [{'signal': s['id'], 'title': s['title'], 'label': s['labels'][company], 'growth': g} for s, g in self.ratios(company, d0, end)]
        if len(used) >= self.cfg['min_signals']:
            vals = [u['growth'] for u in used]
            now = {k: self.roll(company, latest, f(vals), beta) for k, f in [('low', min), ('reference', statistics.median), ('high', max)]}
            as_of, rolled = end, True
        else:
            now, as_of, rolled = {k: float(latest['value_b']) for k in CASES}, d0, False
        total = now['reference']

        rows, seg_name = [], {s['id']: s['name'] for s in self.cfg['segments']}
        row = lambda seg, est, spec, part='public': {'segment': seg, 'name': spec.get('name', seg_name[seg]), 'part': part, 'est': est, 'basis': spec['basis'],
                                                    'cites': spec.get('cites', []), 'evidence': spec.get('evidence'), 'label': spec.get('label'), 'fee_rate': spec.get('fee_rate')}
        for seg in ['consumer', 'advertising']:
            if seg in cfg:
                rows.append(row(seg, self.bounds(cfg[seg], total), cfg[seg]))
        api, fixed = cfg['direct_api'], lambda k: sum(r['est'][k] for r in rows)
        if 'of_business' in api:
            # A share of business revenue. A low subscription figure leaves more business revenue, so extremes are combined consistently.
            f, business = api['of_business'], total - fixed('reference')
            public = {'low': f['low'] * total + (1 - f['low']) * fixed('low'), 'high': f['high'] * total + (1 - f['high']) * fixed('high')}
            rows.append(row('direct_api', {'low': business * f['low'], 'reference': business * (f['low'] + f['high']) / 2, 'high': business * f['high']}, api) | {'of_business': f})
        else:
            rows.append(row('direct_api', self.bounds(api, total), api))
            public = {k: sum(r['est'][k] for r in rows) for k in ['low', 'high']}
        public['reference'] = sum(r['est']['reference'] for r in rows)
        residual = {'low': total - public['high'], 'reference': total - public['reference'], 'high': total - public['low']}
        rows.append(row('enterprise_cloud', residual, cfg['residual'], 'residual'))

        # Signal-implied run rate between reports: last report on or before each week, rolled forward with the fitted elasticity.
        curve, day = [], D(h[0]['obs_date'])
        while day <= max(end, d0):
            base = max((a for a in h if D(a['obs_date']) <= day), key=lambda a: a['obs_date'])
            r = 1.0 if D(base['obs_date']) == day else self.composite(company, D(base['obs_date']), day)
            if r:
                curve.append([str(day), round(self.roll(company, base, r, beta), 2)])
            day += dt.timedelta(days=7)

        # Outlook: no compounding. Either growth stops, or the company keeps adding the dollars per month it averaged across its 2026 reports.
        target = D(self.cfg['outlook_target'])
        per_month = (h[-1]['value_b'] - h[0]['value_b']) / (D(h[-1]['obs_date']) - D(h[0]['obs_date'])).days * 30.4375
        months = (target - as_of).days / 30.4375
        outlook = {'target': str(target), 'months': months, 'added_per_month_b': per_month, 'first': {'id': h[0]['id'], 'value_b': h[0]['value_b'], 'obs_date': h[0]['obs_date']},
                   'flat_b': total, 'steady_b': total + per_month * months}
        return {'latest': {'id': latest['id'], 'value_b': latest['value_b'], 'qualifier': latest['qualifier'], 'obs_date': latest['obs_date']},
                'nowcast': now, 'as_of': str(as_of), 'rolled_forward': rolled, 'signals': used, 'elasticity': fit['elasticity'], 'fit': fit,
                'two_piece': ({'business_share': tp['share'][latest['id']], 'donor': tp['donor'], 'basis': cfg['two_piece']['basis'], 'cites': cfg['two_piece']['cites']} if tp else None),
                'rows': rows, 'public': public, 'residual': residual, 'curve': curve, 'outlook': outlook}

    def per_signal(self):
        """Each signal alone, one for one, against every disclosure. Shows which signals carry information."""
        out = []
        for company in COMPANIES:
            h = self.hist[company]
            for s in self.all_signals:
                if s['kind'] not in ('weekly7', 'daily'):
                    continue
                err = []
                for prev, cur in zip(h, h[1:]):
                    g, _ = growth(s, company, D(prev['obs_date']), D(cur['obs_date']), self.win)
                    if g:
                        err.append((prev['value_b'] * g / cur['value_b'] - 1) * 100)
                if err:
                    out.append({'company': company, 'signal': s['title'], 'in_model': s in self.sig[company], 'n': len(err),
                                'mape': statistics.mean(abs(e) for e in err), 'bias_pct': statistics.mean(err)})
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vintage', help='default: newest data/vintage_* folder')
    args = ap.parse_args()
    vintage = args.vintage or sorted(p.name for p in (ROOT / 'data').glob('vintage_*'))[-1].split('_', 1)[1]
    v = ROOT / 'data' / f'vintage_{vintage}'
    reg = {n: json.loads((ROOT / 'registry' / f'{n}.json').read_text()) for n in ['anchors', 'sources', 'model']}
    anchors, model = reg['anchors']['anchors'], reg['model']

    ids = [a['id'] for a in anchors] + [c['id'] for c in reg['anchors']['context']] + [f['id'] for f in reg['anchors']['forecasts']]
    assert len(ids) == len(set(ids)), 'duplicate register id'
    signals = load_signals(v)
    seg_ids, signal_ids = {s['id'] for s in model['segments']}, {s['id'] for s in signals} | {'anchors', 'snapshots', 'published'}
    for s in reg['sources']['sources']:
        assert set(s['informs']) <= seg_ids, f"{s['id']}: unknown segment {set(s['informs']) - seg_ids}"
        assert s['status'] in ('live', 'planned')
        assert s['status'] == 'live' or not s['signals'], f"{s['id']}: planned sources cannot publish signals"
        assert s['status'] == 'planned' or set(s['signals']) <= signal_ids, f"{s['id']}: live source lists a signal this vintage does not have"
    for c, cfg in model['companies'].items():
        for seg in cfg.values():
            if isinstance(seg, dict):
                assert set(seg.get('cites', [])) <= set(ids), f'{c}: cites an unknown register id'
        assert set(cfg.get('two_piece', {}).get('business_share', {})) <= set(ids), f'{c}: two_piece cites an unknown report'

    m = Model(signals, model, anchors)
    companies = {c: m.company(c) for c in COMPANIES}
    site = {
        'meta': {'vintage': vintage, 'companies': COMPANIES},
        'grades': reg['anchors']['grades'], 'anchors': anchors, 'context': reg['anchors']['context'], 'forecasts': reg['anchors']['forecasts'],
        'signals': [{k: s.get(k) for k in ['id', 'source', 'title', 'unit', 'subtitle', 'note', 'invert', 'log', 'no_index']}
                    | {'in_model': [c for c in COMPANIES if s in m.sig[c]],
                       'series': [{'company': c, 'label': s['labels'][c], 'points': chart_points(s, c, model['window_days'])} for c in COMPANIES]} for s in signals],
        'snapshots': read(v / 'snapshots.csv'),
        'published': {k: x for k, x in json.loads((ROOT / 'registry' / 'published.json').read_text()).items() if not k.startswith('_')},
        'model': {'reviewed': model['reviewed'], 'window_days': model['window_days'], 'min_signals': model['min_signals'], 'segments': model['segments'], 'companies': companies},
        'per_signal': m.per_signal(), 'sources': reg['sources']['sources'],
    }

    out = ROOT / 'site' / 'data'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'site.json').write_text(json.dumps(site, separators=(',', ':')))
    csv_out = out / 'csv'
    if csv_out.exists():
        shutil.rmtree(csv_out)
    csv_out.mkdir()
    for f in sorted(v.glob('*.csv')) + [v / 'manifest.json']:
        if f.exists() and f.stat().st_size < 400_000:  # the per-model Ramp file stays in the repository only
            shutil.copy(f, csv_out / f.name)
    for n in ['anchors', 'sources', 'model', 'published']:
        shutil.copy(ROOT / 'registry' / f'{n}.json', out / f'{n}.json')
    r1 = lambda d: {k: round(x, 1) for k, x in d.items()}
    print(json.dumps({'vintage': vintage, 'companies': {c: {
        'latest': x['latest'], 'as_of': x['as_of'], 'rolled': x['rolled_forward'], 'elasticity': round(x['elasticity'], 3), 'nowcast': r1(x['nowcast']),
        'signals': [(u['signal'], round(u['growth'], 3)) for u in x['signals']], 'public': r1(x['public']), 'residual': r1(x['residual']),
        'rows': {r['segment']: r1(r['est']) for r in x['rows']},
        'methods': [(q['method'], q['n'], round(q['mape'], 1), round(q['bias_pct'], 1)) for q in x['fit']['methods']],
        'pairs': [(p['to'], round(p['signal_ratio'], 2), round(p['actual_b'] / p['prev_b'], 2), p['model_b'] and round(p['model_b'], 1)) for p in x['fit']['pairs']],
        'outlook': {k: round(v, 1) for k, v in x['outlook'].items() if isinstance(v, float)}, 'curve_n': len(x['curve'])} for c, x in companies.items()},
        'per_signal': [(p['company'], p['signal'], p['n'], round(p['mape'], 1), round(p['bias_pct'], 1)) for p in site['per_signal']]}, indent=1))


if __name__ == '__main__':
    main()

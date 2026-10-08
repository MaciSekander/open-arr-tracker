"""Collect one dated vintage of every live public source. Standard library, no credentials.

    python3 pipeline/collect.py --end 2026-10-03 [--carry-tranco data/vintage_2026-09-22]

Writes data/vintage_<today>/ with raw responses (URL, timestamp, hash) and tidy CSVs.
Pass --carry-tranco with the previous vintage: its sampled ranks are kept and one new list per week is added, and
any secondary source that fails is carried forward from it. Only npm and Ramp failing stops the run.
Sources revise history, so keep every vintage.
"""
import argparse, csv, datetime as dt, json, shutil, sys, time, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'collectors'))
import collect_signals  # noqa: E402
from collect_signals import fetch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

NPM = ['openai', '@anthropic-ai/sdk', '@ai-sdk/openai', '@ai-sdk/anthropic', '@openai/codex', '@anthropic-ai/claude-code']
PYPI = ['openai', 'anthropic']
WIKI = ['ChatGPT', 'Claude_(language_model)', 'Claude_(AI)']  # the Claude article was renamed; both titles are summed
BREW_CASKS = ['codex', 'claude-code', 'claude-code@latest', 'chatgpt', 'claude']
OPEN_VSX = ['openai/chatgpt', 'Anthropic/claude-code']
GITHUB = ['openai/codex', 'anthropics/claude-code', 'openai/openai-python', 'anthropics/anthropic-sdk-python']
CORE = ['npm', 'ramp']
CARRY_FILES = {'pypi': 'pypi_daily.csv', 'wikipedia': 'wikipedia_daily.csv', 'tranco': 'tranco_sampled.csv'}
APPLE_COUNTRIES = ['us', 'gb', 'de', 'jp', 'in', 'br']
APPLE_APPS = {'ChatGPT': 'OpenAI', 'Claude by Anthropic': 'Anthropic'}
APPLE_IDS = {'ChatGPT': 6448311069, 'Claude by Anthropic': 6473753684}


def write(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def slug(s):
    return ''.join(c if c.isalnum() else '_' for c in s).strip('_')


def npm(start, end, out):
    rows = []
    for pkg in NPM:
        url = f'https://api.npmjs.org/downloads/range/{start}:{end}/{urllib.parse.quote(pkg, safe="@/")}'
        raw = json.loads(fetch(url, out / 'raw' / f'npm_{slug(pkg)}.json.gz'))
        if raw.get('package') != pkg:
            raise ValueError(f'npm: unexpected package in response for {pkg}')
        days = {d['day']: d['downloads'] for d in raw['downloads']}
        if len(days) != len(raw['downloads']):
            raise ValueError(f'npm: duplicate days for {pkg}')
        for day, n in sorted(days.items()):
            # npm returns 0 for days it has not counted; keep the raw value and flag it.
            rows.append({'date': day, 'package': pkg, 'downloads_raw': n, 'quality_flag': 'observed_positive' if n > 0 else 'zero_unverified'})
    write(out / 'npm_daily.csv', rows)
    return len(rows)


def pypi(out):
    rows = []
    for i, pkg in enumerate(PYPI):
        time.sleep(20 if i else 0)  # pypistats rate-limits bursts
        raw = json.loads(fetch(f'https://pypistats.org/api/packages/{pkg}/overall?mirrors=false', out / 'raw' / f'pypi_{slug(pkg)}.json.gz'))
        for d in sorted(raw['data'], key=lambda d: d['date']):
            if d['category'] == 'without_mirrors':
                rows.append({'date': d['date'], 'package': pkg, 'downloads': d['downloads']})
    write(out / 'pypi_daily.csv', rows)
    return len(rows)


def wikipedia(start, end, out):
    rows = []
    for art in WIKI:
        url = ('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/'
               f'{urllib.parse.quote(art, safe="")}/daily/{start:%Y%m%d}/{end:%Y%m%d}')
        raw = json.loads(fetch(url, out / 'raw' / f'wikipedia_{slug(art)}.json.gz'))
        for it in raw['items']:
            t = it['timestamp']
            rows.append({'date': f'{t[:4]}-{t[4:6]}-{t[6:8]}', 'article': art, 'views': it['views']})
    write(out / 'wikipedia_daily.csv', rows)
    return len(rows)


def snapshots(out, carry=None):
    """Sources with no public history. Each run adds one observation; trends build up across vintages.

    Each source is collected on its own: one that fails is carried forward from the previous vintage and reported.
    """
    def homebrew():
        rows = []
        for window in ['30d', '90d', '365d']:
            raw = json.loads(fetch(f'https://formulae.brew.sh/api/analytics/cask-install/{window}.json', out / 'raw' / f'homebrew_cask_{window}.json.gz'))
            found = {it['cask']: int(it['count'].replace(',', '')) for it in raw['items'] if it['cask'] in BREW_CASKS}
            rows += [{'source': 'homebrew', 'item': cask, 'metric': f'installs_{window}', 'value': found.get(cask, ''), 'period_start': raw['start_date'], 'period_end': raw['end_date']} for cask in BREW_CASKS]
        return rows

    def open_vsx():
        return [{'source': 'open_vsx', 'item': ext, 'metric': 'downloads_cumulative', 'period_start': '', 'period_end': '',
                 'value': json.loads(fetch(f'https://open-vsx.org/api/{ext}', out / 'raw' / f'openvsx_{slug(ext)}.json.gz'))['downloadCount']} for ext in OPEN_VSX]

    def github():
        return [{'source': 'github', 'item': repo, 'metric': 'stars_cumulative', 'period_start': '', 'period_end': '',
                 'value': json.loads(fetch(f'https://api.github.com/repos/{repo}', out / 'raw' / f'github_{slug(repo)}.json.gz'))['stargazers_count']} for repo in GITHUB]

    def apple_top_free():
        # Apple's newer chart feed times out now and then; the older iTunes feed carries the same chart, so it is the fallback.
        rows, ids = [], {str(v): k for k, v in APPLE_IDS.items()}
        for cc in APPLE_COUNTRIES:
            try:
                raw = json.loads(fetch(f'https://rss.marketingtools.apple.com/api/v2/{cc}/apps/top-free/100/apps.json', out / 'raw' / f'apple_topfree_{cc}.json.gz'))
                order = [str(r['id']) for r in raw['feed']['results']]
            except Exception:
                raw = json.loads(fetch(f'https://itunes.apple.com/{cc}/rss/topfreeapplications/limit=100/json', out / 'raw' / f'apple_topfree_{cc}_itunes.json.gz'))
                order = [e['id']['attributes']['im:id'] for e in raw['feed']['entry']]
            rank = {ids[x]: i + 1 for i, x in enumerate(order) if x in ids}
            rows += [{'source': 'apple_top_free', 'item': f'{app} ({cc})', 'metric': 'rank_top100', 'value': rank.get(app, ''), 'period_start': '', 'period_end': ''} for app in APPLE_APPS]
        return rows

    def apple_ratings():
        # Cumulative App Store ratings: no history is published, so growth appears only across vintages.
        rows = []
        for cc in APPLE_COUNTRIES:
            raw = json.loads(fetch(f'https://itunes.apple.com/lookup?id={",".join(str(i) for i in APPLE_IDS.values())}&country={cc}', out / 'raw' / f'apple_lookup_{cc}.json.gz'))
            count = {r['trackId']: r.get('userRatingCount') for r in raw['results']}
            rows += [{'source': 'apple_ratings', 'item': f'{app} ({cc})', 'metric': 'ratings_cumulative', 'value': count.get(app_id, ''), 'period_start': '', 'period_end': ''} for app, app_id in APPLE_IDS.items()]
        return rows

    previous = []
    if carry and (carry / 'snapshots.csv').exists():
        with (carry / 'snapshots.csv').open() as f:
            previous = list(csv.DictReader(f))
    rows, failed = [], {}
    for name, step in [('homebrew', homebrew), ('open_vsx', open_vsx), ('github', github), ('apple_top_free', apple_top_free), ('apple_ratings', apple_ratings), ('openrouter', lambda: openrouter(out))]:
        try:
            rows += step()
        except Exception as e:
            failed[name] = f'{type(e).__name__}: {e}'
            rows += [r for r in previous if r['source'] == name]
    write(out / 'snapshots.csv', rows)
    return {'rows': len(rows), 'carried_forward_after_failure': failed}


def openrouter(out):
    """Top-20 models and apps by tokens over the past week, from the public rankings page."""
    import collect_ramp as cr
    body = fetch('https://openrouter.ai/rankings', out / 'raw' / 'openrouter_rankings.html.gz').decode()
    flight = ''.join(x for m in __import__('re').finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', body)
                     for x in _strings(m[1]))
    state, _ = json.JSONDecoder().raw_decode(flight[flight.index('{"mutations"'):])
    data = {json.dumps(q.get('queryKey')): q['state']['data'] for q in state['queries'] if 'queryKey' in q}
    models = data['["rankings", "models", {"view": "week"}]']
    tokens = lambda r: r['total_prompt_tokens'] + r['total_completion_tokens']
    total = sum(tokens(r) for r in models)
    week = max(r['date'] for r in models)[:10]
    rows = []
    for author, lab in [('openai', 'OpenAI'), ('anthropic', 'Anthropic')]:
        mine = sum(tokens(r) for r in models if r['model_permaslug'].startswith(author + '/'))
        rows.append({'source': 'openrouter', 'item': f'{lab} models in the top {len(models)}', 'metric': 'token_share_week_pct', 'value': round(100 * mine / total, 1), 'period_start': '', 'period_end': week})
    apps = {a['app']['title']: int(a['total_tokens']) for a in data['["rankings", "apps"]']['week']}
    for title in ['Codex', 'Claude Code']:
        rows.append({'source': 'openrouter', 'item': f'{title} app', 'metric': 'tokens_week', 'value': apps.get(title, ''), 'period_start': '', 'period_end': week})
    return rows


def _strings(chunk):
    try:
        return [x for x in json.loads(chunk) if isinstance(x, str)]
    except json.JSONDecodeError:
        return []


def tranco(end, out, carry):
    """Carry the previous vintage's sampled ranks and add one list per week since its last date."""
    with (carry / 'tranco_sampled.csv').open() as f:
        rows = list(csv.DictReader(f))
    day, added = dt.date.fromisoformat(max(r['date'] for r in rows)) + dt.timedelta(days=7), 0
    while day <= end:
        rows += collect_signals.collect_tranco(day, out); added += 1
        day += dt.timedelta(days=7)
    write(out / 'tranco_sampled.csv', rows)
    return f'{added} new weekly lists added to {carry.name}'


def ramp(start, end, out):
    import collect_ramp as cr
    body = fetch('https://ramp.com/data/ai-index', out / 'raw' / 'ramp_index.html.gz').decode()
    arrays = {k: cr.extract(body, k) for k in ['tokenPrices', 'tokenVolumes', 'adoptionVendor']}
    labs = ['openai', 'anthropic']
    daily = [r for r in arrays['tokenPrices'] if str(start) <= r['usage_date'] <= str(end) and r['model_maker'] in labs]
    keys = [(r['usage_date'], r['model_maker'], r['token_type']) for r in daily]
    if len(keys) != len(set(keys)):
        raise ValueError('ramp: duplicate daily token observation')
    adoption = [r for r in arrays['adoptionVendor'] if str(start) <= r['date_month'] <= str(end) and r['vendor'] in ['OpenAI', 'Anthropic']]
    weekly = [r for r in arrays['tokenVolumes'] if str(start) <= r['period_start'] and r['period_end'] <= str(end) and r['model_maker'] in labs]
    cr.write(out / 'ramp_token_daily_7d.csv', daily); cr.write(out / 'ramp_adoption_monthly.csv', adoption); cr.write(out / 'ramp_token_weekly_models.csv', weekly)
    return {'latest_token_date': max(r['usage_date'] for r in daily), 'latest_adoption_month': max(r['date_month'] for r in adoption),
            'latest_week_end': max(r['period_end'] for r in weekly), 'rows': len(daily) + len(adoption) + len(weekly)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--start', type=dt.date.fromisoformat, default=dt.date(2025, 12, 1))
    ap.add_argument('--end', type=dt.date.fromisoformat, required=True, help='last complete day to request')
    ap.add_argument('--vintage', default=str(dt.date.today()))
    ap.add_argument('--carry-tranco', type=Path)
    ap.add_argument('--only', help='comma-separated sources to (re)collect into an existing vintage')
    a = ap.parse_args()
    out = ROOT / 'data' / f'vintage_{a.vintage}'
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / 'manifest.json'
    report = json.loads(manifest.read_text()) if a.only and manifest.exists() else {'vintage': a.vintage, 'requested': [str(a.start), str(a.end)], 'sources': {}}
    src = (a.carry_tranco if a.carry_tranco.is_absolute() else ROOT / a.carry_tranco) if a.carry_tranco else None
    steps = {'npm': lambda: npm(a.start, a.end, out), 'pypi': lambda: pypi(out), 'wikipedia': lambda: wikipedia(a.start, a.end, out),
             'snapshots': lambda: snapshots(out, src), 'ramp': lambda: ramp(a.start, a.end, out)}
    if src:
        steps['tranco'] = lambda: tranco(a.end, out, src)
    if a.only:
        steps = {k: steps[k] for k in a.only.split(',')}
    for name, step in steps.items():
        try:
            report['sources'][name] = {'ok': True, 'result': step()}
        except Exception as e:  # never dropped silently: recorded in the manifest, and the last good file is carried forward
            report['sources'][name] = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
            f = CARRY_FILES.get(name)
            if f and src and (src / f).exists() and src != out:
                shutil.copy(src / f, out / f)
                report['sources'][name]['carried_forward_from'] = src.name
    manifest.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    # The estimates need npm and Ramp. Anything else can lag a week without breaking the site.
    sys.exit(0 if all(report['sources'].get(k, {}).get('ok', a.only is not None) for k in CORE) else 1)

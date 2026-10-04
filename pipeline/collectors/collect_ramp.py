"""Public embedded Ramp aggregates; no credentials or private records.

python3 scripts/collect_ramp.py --end 2026-09-21 --input data/final_research/raw/ramp_index.html.gz
Omit --input for a fresh dated snapshot. Preserve vintages; revised history is not an as-of backtest.
"""
import argparse, csv, datetime as dt, gzip, json, re
from pathlib import Path
from collect_signals import fetch

def extract(html, key):
    chunks = []
    for match in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>', html):
        try:
            chunks.extend(x for x in json.loads(match[1]) if isinstance(x, str))
        except json.JSONDecodeError:
            continue
    text = ''.join(chunks)
    marker = '"' + key + '":'
    if text.count(marker) != 1:
        raise ValueError(f'Ambiguous or missing source array: {key}')
    result = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])[0]
    if not isinstance(result, list) or not result:
        raise ValueError('Empty source array')
    return result

def write(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--start', default='2025-12-01'); p.add_argument('--end', required=True)
    p.add_argument('--input'); p.add_argument('--output', default='data/final_research')
    a = p.parse_args(); root = Path(a.output); root.mkdir(parents=True, exist_ok=True)
    if a.input:
        body = gzip.decompress(Path(a.input).read_bytes())
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        body = fetch('https://ramp.com/data/ai-index', root/'raw'/f'ramp_{stamp}.html.gz')
    arrays = {k: extract(body.decode(), k) for k in ['tokenPrices','tokenVolumes','adoptionVendor']}
    for key, rows in arrays.items():
        (root / (key+'_full.json')).write_text(json.dumps(rows, indent=2))
    daily = [r for r in arrays['tokenPrices'] if a.start <= r['usage_date'] <= a.end and r['model_maker'] in ['openai','anthropic']]
    seen = set()
    for r in daily:
        key = (r['usage_date'],r['model_maker'],r['token_type'])
        if key in seen or r['token_count_7d'] <= 0 or r['token_cost_usd_7d'] < 0:
            raise ValueError(f'Invalid token observation: {key}')
        seen.add(key)
    adoption = [r for r in arrays['adoptionVendor'] if a.start <= r['date_month'] <= a.end and r['vendor'] in ['OpenAI','Anthropic']]
    weekly = [r for r in arrays['tokenVolumes'] if a.start <= r['period_start'] and r['period_end'] <= a.end and r['model_maker'] in ['openai','anthropic']]
    write(root/'ramp_token_daily_7d.csv',daily); write(root/'ramp_adoption_monthly.csv',adoption); write(root/'ramp_token_weekly_models.csv',weekly)
    report = {'source':'https://ramp.com/data/ai-index','requested_start':a.start,'requested_end':a.end,
              'latest_token_date':max(r['usage_date'] for r in daily),'latest_adoption_month':max(r['date_month'] for r in adoption),
              'rows':{'token_daily_7d':len(daily),'adoption':len(adoption),'weekly_models':len(weekly)},
              'basis':'TSM connected-provider usage and billing sample; not whole Ramp population or lab recognized revenue',
              'warning':'Do not sum overlapping daily seven-day windows or all_tokens with its components. Latest vintage, not historical publication snapshots.'}
    (root/'ramp_manifest.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))

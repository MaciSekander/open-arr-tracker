"""Public npm and Tranco collection. Standard-library only; no credentials required.

Run: python3 scripts/collect_signals.py --start 2025-12-01 --end 2026-09-21
Raw responses, request metadata and derived observations are retained by run.
"""
import argparse
import calendar
import concurrent.futures
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
import zipfile

PACKAGES = ['openai', '@anthropic-ai/sdk', '@openai/codex', '@anthropic-ai/claude-code']
DOMAINS = ['chatgpt.com', 'openai.com', 'claude.ai', 'anthropic.com']

def fetch(url, path):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'open-arr-tracker/1.0 (public research)'})
            with urllib.request.urlopen(request, timeout=60) as r:
                data = r.read()
                meta = {'url': url, 'retrieved_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                        'status': r.status, 'headers': {k: v for k, v in r.headers.items() if k.lower() != 'set-cookie'},
                        'sha256_uncompressed_response': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(data))
            path.with_suffix(path.suffix + '.meta.json').write_text(json.dumps(meta, indent=2))
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def dates(start, end):
    while start <= end:
        yield start
        start += dt.timedelta(days=1)

def collect_npm(package, start, end, root):
    slug = package.replace('@','').replace('/','_')
    url = f'https://api.npmjs.org/downloads/range/{start}:{end}/{urllib.parse.quote(package, safe="@/")}'
    raw = json.loads(fetch(url, root / 'raw' / f'npm_{slug}.json.gz'))
    if raw.get('package') != package or raw.get('start') != str(start) or raw.get('end') != str(end):
        raise ValueError(f'Unexpected npm response metadata: {package}')
    rows = raw['downloads']
    seen = set()
    result = []
    for row in rows:
        day, count = row['day'], row['downloads']
        if day in seen or not isinstance(count, int) or count < 0 or not start <= dt.date.fromisoformat(day) <= end:
            raise ValueError(f'Invalid observation {package}: {row}')
        seen.add(day)
        result.append({'date': day, 'package': package, 'downloads_raw': count,
                       'quality_flag': 'zero_unverified' if count == 0 else 'observed_positive'})
    for day in dates(start, end):
        if str(day) not in seen:
            result.append({'date': str(day), 'package': package, 'downloads_raw': '', 'quality_flag': 'missing'})
    return result

def collect_tranco(day, root):
    url = f'https://tranco-list.eu/api/lists/date/{day:%Y%m%d}'
    meta = json.loads(fetch(url, root / 'raw' / f'tranco_{day}_metadata.json.gz'))
    if not meta.get('available') or meta.get('failed'):
        raise ValueError(f'Tranco unavailable for {day}')
    if meta.get('configuration', {}).get('endDate') != str(day):
        raise ValueError(f'Tranco date mismatch for {day}')
    raw = fetch(meta['download'], root / 'raw' / f'tranco_{day}_{meta["list_id"]}.response.gz')
    if raw.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = [n for n in archive.namelist() if n.endswith('.csv')]
            if len(names) != 1: raise ValueError('Ambiguous CSV in Tranco archive')
            raw = archive.read(names[0])
    found = {}
    count = 0
    for row in csv.reader(io.StringIO(raw.decode('utf-8-sig'))):
        if len(row) != 2: raise ValueError('Invalid Tranco row')
        rank = int(row[0])
        count += 1
        if rank != count: raise ValueError('Unexpected rank sequence')
        if row[1] in DOMAINS: found[row[1]] = rank
    if count < 100000: raise ValueError(f'Tranco unexpectedly short: {count}')
    return [{'date': str(day), 'domain': domain, 'rank': found.get(domain, ''),
             'quality_flag': 'observed' if domain in found else 'absent_from_list',
             'list_id': meta['list_id'], 'list_rows': count,
             'window_start': meta['configuration'].get('startDate'),
             'window_end': meta['configuration'].get('endDate'),
             'providers': '|'.join(meta['configuration'].get('providers', []))} for domain in DOMAINS]

def write_csv(path, rows, fields):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=dt.date.fromisoformat, required=True)
    parser.add_argument('--end', type=dt.date.fromisoformat, required=True)
    parser.add_argument('--output', type=Path, default=Path('data'))
    args = parser.parse_args()
    if args.start > args.end: parser.error('start must be <= end')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = args.output / f'collection_{stamp}'
    root.mkdir(parents=True, exist_ok=False)
    npm, tranco, errors = [], [], []
    # Month-end observations for the long history; extra weekly dates in the final
    # 42 days. The Tranco underlying window is itself smoothed, not point traffic.
    samples = {args.start, args.end}
    for day in dates(args.start, args.end):
        if day.day == calendar.monthrange(day.year, day.month)[1]: samples.add(day)
        if day >= args.end - dt.timedelta(days=42) and day.weekday() == 3: samples.add(day)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(collect_npm, p, args.start, args.end, root): ('npm', p) for p in PACKAGES}
        for job in concurrent.futures.as_completed(jobs):
            kind, label = jobs[job]
            try:
                rows = job.result()
                npm.extend(rows)
                print(f'{label}: {len(rows)} rows', flush=True)
            except Exception as e: errors.append({'source': kind, 'label': label, 'error': str(e)})
    for day in sorted(samples):
        try:
            rows = collect_tranco(day, root)
            tranco.extend(rows)
            print(f'Tranco {day}: ' + ', '.join(f'{r["domain"]}={r["rank"]}' for r in rows), flush=True)
        except Exception as e:
            errors.append({'source': 'tranco', 'label': str(day), 'error': str(e)})
            print(f'Tranco {day}: FAILED {e}', flush=True)
        time.sleep(1.1)
    write_csv(root/'npm_daily.csv', sorted(npm, key=lambda r:(r['package'],r['date'])),
              ['date','package','downloads_raw','quality_flag'])
    write_csv(root/'tranco_sampled.csv', tranco,
              ['date','domain','rank','quality_flag','list_id','list_rows','window_start','window_end','providers'])
    manifest = {'start':str(args.start),'end':str(args.end),'npm_packages':PACKAGES,
                'tranco_domains':DOMAINS,'tranco_sample_dates':[str(d) for d in sorted(samples)],
                'errors':errors,'npm_rows':len(npm),'tranco_rows':len(tranco),
                'note':'Zero npm counts retained and flagged, not imputed. No revenue conversion.'}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'output':str(root),'errors':errors}), flush=True)

if __name__ == '__main__': main()

# Open ARR Tracker

**Live site: https://macisekander.github.io/open-arr-tracker/**

Open-source estimates of OpenAI and Anthropic annualized revenue (run rate), built only from public
disclosures and public alternative data. Every input, assumption and error is published.

Not affiliated with OpenAI or Anthropic. Estimates are conditional on stated assumptions. They are not
audited figures and not investment advice.

## How it works

1. **Total run rate.** Start from each lab's latest reported figure. Move it by the median growth of its activity
   signals since that report, raised to an elasticity fitted on Anthropic's report history. For OpenAI only the
   business share moves; consumer revenue is held at its last reported level. No hand-set growth rates.
2. **Part 1, publicly traceable.** Subscriptions, advertising and direct API. Each is bounded by a cited
   disclosure; the default is the midpoint. A segment with no disclosure is labelled as a placeholder.
3. **Part 2, not observable.** Enterprise contracts and cloud resale: the total minus Part 1.
4. **Outlook.** Three cases with no compounding: growth stops, the lab keeps adding the dollars per month it
   averaged across its 2026 reports, or it keeps the pace between its last two reports. Published expectations are shown beside them and never used in the maths.

## What is here

| Path | Purpose |
|---|---|
| `registry/anchors.json` | Reported disclosures: exact wording, dates, link, evidence grade A to D |
| `registry/sources.json` | Catalogue of data sources, `live` (collected) or `planned` |
| `registry/published.json` | Cloud earnings and gateway figures transcribed from published reports (context only) |
| `registry/model.json` | Segments, which signals drive each one, starting shares and fallback assumptions |
| `data/vintage_YYYY-MM-DD/` | One dated collection: tidy CSVs, a manifest, and the URL, timestamp and hash of every raw response (the raw bodies stay local) |
| `pipeline/collect.py` | Collects every live source (standard library, no credentials) |
| `pipeline/build.py` | Validates registries, computes signals, the model and accuracy checks, writes `site/data/` |
| `tests/` | Checks on the model maths and collectors (standard library `unittest`) |
| `site/` | Static site. No build step, no dependencies |

## Run it

```bash
python3 pipeline/collect.py --end 2026-10-03 --carry-tranco data/vintage_2026-09-22   # new vintage; pass the previous one
python3 -m unittest discover tests
python3 pipeline/build.py
python3 pipeline/serve.py 8000
```

Requires Python 3.9+. `collect.py --only pypi` re-collects one source into an existing vintage (PyPI rate-limits).
`--carry-tranco` keeps the previous vintage's sampled ranks and adds one new list per week.

## Current state (vintage 2026-11-02, signals through 23 October)

| | Run rate (likely range) | Part 1, publicly traceable | Part 2, residual | Year-end outlook |
|---|---|---|---|---|
| OpenAI | $74.7B ($55B to $101B) | $49.9B (28.4 to 65.3) | $24.7B (9.3 to 46.3) | $75B to $87B; $120B at the recent pace |
| Anthropic | $128.5B ($112B to $148B) | $63.0B (51.4 to 74.5) | $65.6B (54.0 to 77.1) | $129B to $153B; $178B at the recent pace |

- Latest reports: OpenAI about $70B (29 September), Anthropic more than $100B (18 September). Both are grade C.
- Anthropic's split rests on 2025 figures Reuters reported from its IPO prospectus: subscriptions 17% of revenue,
  47% of sales through Amazon and Google.
- OpenAI has not disclosed how business revenue divides, so its direct API share is a labelled placeholder.
- Accuracy, predicting each report from the one before in real time: Anthropic misses averaged 12% over six reports
  (trend line 18%, no change 33%). OpenAI's two-piece model missed 21% over two reports, against 49% as one business.
- The likely range is the reference moved by the typical past miss (Anthropic ±15%, OpenAI ±35%). Checked by leaving
  each report out, it held 3 of 6 Anthropic reports and 1 of 2 OpenAI reports.
- Token economics (Ramp sample, December to October, on Ramp's revised token counts): Anthropic tokens up 21x at a
  59% lower billed price per token, so spend up 8.7x. OpenAI tokens up 8.2x at a 23% lower price, spend up 6.3x.
- PyPI is collected but never measured across 24 August 2026, where both SDKs step down about 38%.

## Forecast checks

`python3 -m unittest discover tests` runs in both workflows before anything is built or committed. It checks that:

- the backtest is real time: the elasticity for each report is fitted only on earlier reports, and OpenAI's borrowed
  elasticity uses only earlier Anthropic reports (previously leave-one-out, which let later reports inform earlier
  predictions);
- the likely range is sized by past misses, not by the spread between signals (that spread contained the reported
  figure in only 3 of 9 past reports), and never drops below a "more than" report;
- the signal-implied line ends on the headline date and value;
- Part 1 plus Part 2 equals the total, and every outlook case is plain arithmetic.

## Updating

`.github/workflows/collect.yml` collects a new vintage every Monday and rebuilds the site; the total then rolls
forward with the signals on its own. Two things still need a person: adding new reports to
`registry/anchors.json` with exact wording and a grade, and revisiting the bounds in `registry/model.json` when a
new disclosure changes them. If the weekly run fails, the manifest printed in its log names the source and the error.

Ramp stopped embedding its token series in the AI Index page in late October 2026; the collector now falls back to
the page's own `chart-data` endpoint and fails loudly if the fields it reads ever change. The new feed also revised history:
`all_tokens` now includes more cached tokens (Anthropic up to 1.8x, OpenAI 1.1x by October 2026, almost nothing in
December 2025), so token growth in vintages from 2026-11-02 on is not comparable with earlier vintages. Output and
fresh-input tokens did not change.

## Licence

Code: MIT. Registry files: CC BY 4.0. Third-party data stays under its publisher's terms; check them before
redistributing or automating collection.

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
4. **Outlook.** Two cases with no compounding: growth stops, or the lab keeps adding the dollars per month it
   averaged across its 2026 reports. Published expectations are shown beside them and never used in the maths.

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
| `site/` | Static site. No build step, no dependencies |

## Run it

```bash
python3 pipeline/collect.py --end 2026-10-03 --carry-tranco data/vintage_2026-09-22   # new vintage; pass the previous one
python3 pipeline/build.py
python3 pipeline/serve.py 8000
```

Requires Python 3.9+. `collect.py --only pypi` re-collects one source into an existing vintage (PyPI rate-limits).
`--carry-tranco` keeps the previous vintage's sampled ranks and adds one new list per week.

## Current state (vintage 2026-10-04, signals through 29 September)

| | Run rate | Part 1, publicly traceable | Part 2, residual | Year-end outlook |
|---|---|---|---|---|
| OpenAI | $70.0B | $47.0B (27.3 to 61.3) | $23.0B (8.7 to 42.8) | $70B to $87B |
| Anthropic | $107.1B (95.6 to 112.3) | $52.5B (42.8 to 62.1) | $54.6B (45.0 to 64.3) | $107B to $140B |

- Latest reports: OpenAI about $70B (29 September), Anthropic more than $100B (18 September). Both are grade C.
- Anthropic's split rests on 2025 figures Reuters reported from its IPO prospectus: subscriptions 17% of revenue,
  47% of sales through Amazon and Google.
- OpenAI has not disclosed how business revenue divides, so its direct API share is a labelled placeholder.
- Accuracy, predicting each report from the one before: Anthropic misses averaged 13% over six reports (trend
  line 18%, no change 33%).
- OpenAI is modelled in two pieces because its mix shifted in 2026: business revenue moves with developer signals
  including Codex, consumer revenue is held at its last reported level. Typical miss 18% over two reports, against
  31% as one business. It still fell a third short of the September report, when consumer revenue also jumped.
- PyPI is collected but never measured across 24 August 2026, where both SDKs step down about 38%.

## Updating

`.github/workflows/collect.yml` collects a new vintage every Monday and rebuilds the site; the total then rolls
forward with the signals on its own. Two things still need a person: adding new reports to
`registry/anchors.json` with exact wording and a grade, and revisiting the bounds in `registry/model.json` when a
new disclosure changes them. The workflows have not been run yet; check the first run.

## Licence

Code: MIT. Registry files: CC BY 4.0. Third-party data stays under its publisher's terms; check them before
redistributing or automating collection.

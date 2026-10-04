# Contributing

## Add or correct a disclosure

Edit `registry/anchors.json`.

- One entry per disclosure, not per article.
- Quote the exact wording in `excerpt` (short), and link the page you actually read.
- Keep the real precision: `>` for "more than", `~` for "about". Record both observation and publication dates.
- Grade how you read it: A company statement, B original journalism, C republication, D unresolved.
- Product or segment figures are never added to a company total.

## Add a data source

1. Add an entry to `registry/sources.json` with `status: "planned"`, what it measures, and its blind spot.
2. Write a step in `pipeline/collect.py`: standard library only, no credentials, save the raw response
   with URL, timestamp and hash.
3. Add the series in `pipeline/build.py` (`load_signals`), list it under `segment_signals` in `registry/model.json` if it should drive growth, and set the source to `live`. Declare any known counting break in `breaks`.
4. Only public, aggregate data. No paid datasets, no row-level customer or personal records, and respect each
   site's terms and rate limits.

## Change the model

Edit `registry/model.json`. Every bound must cite a register id and say in one sentence how it follows from that
disclosure. If nothing is disclosed, set `evidence` to `none` so the site labels the default as a placeholder.
Do not add growth assumptions: totals move only with reports and fitted signals, and the outlook does not compound.

## Before opening a pull request

```bash
python3 pipeline/build.py
```

It must pass, and the site must load with no console errors.

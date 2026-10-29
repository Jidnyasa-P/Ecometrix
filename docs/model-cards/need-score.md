# Model card: need score (M5)

**Code:** `model/need_score.py` · **Output:** `analysis.parquet` (`need_*` columns), `need_report.json`

| | |
|---|---|
| Question | Where would additional green space matter most? |
| Components | Percentile ranks (0 to 1) across populated hexagons: **heat** (surface temperature), **people** (residents 2020), **gap** (1 minus share of residents within 300 m of a mapped park of at least 0.5 ha), **growth** (projected people added by 2035) |
| Score | Weighted mean of the available components, scaled 0 to 100. Weights are renormalised over components that exist. Hexagons with no modelled residents get no score. |
| Weights | **Policy choices, not facts.** Four presets in `config/pilot_pune.yaml` (balanced, heat first, access first, growth aware); users can set their own on the Priority page. |
| Checks | Spearman correlation and top-decile overlap between presets; the share of top-decile hexagons that stay top-decile under every preset ("no-regret") |
| Not included | Vulnerability of residents (age, income, health): no open data built for it. Land availability is handled separately by candidate sites. |
| Limits | Percentile ranks are relative: a high score means "high compared with the rest of Pune", not "high in absolute terms". |

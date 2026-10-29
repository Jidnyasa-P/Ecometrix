# model/

Analytical modules. All run from `python model/run_models.py` after the pipeline (reads `data/outputs`).

| Module | Milestone | File | Status |
|---|---|---|---|
| NDVI vs surface-temperature baseline | M3 | `baseline_relationship.py` | Built |
| Heat–greenery model (spatial CV vs simple baselines, monotonic constraints, bootstrap ranges) | M4 | `heat_model.py` | Built |
| Demand forecast (backtest, error envelope) | M5 | `forecast.py` | Built |
| Need score (four components, presets, stability) | M5 | `need_score.py` | Built |
| Candidate sites (pocket park, mini-forest) | M5 | `sites.py` | Built |
| Budget-constrained portfolio optimiser | M6 | n/a | Not built |

Model cards: `docs/model-cards/`. Rules: every model is compared with a simple baseline and kept only if it wins; validation uses spatial block cross-validation; no accuracy figure is published before it comes from such a test.

```bash
pip install -r model/requirements.txt
python model/run_models.py
python -m pytest model/tests
```
The cost and impact engine for one site lives in `backend/app/engine/` (it reads `config/assumptions.yaml`).

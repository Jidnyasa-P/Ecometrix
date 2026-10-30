# EcoMetrix model layer

Run from the repository root after the selected city's data pipeline has completed:

```powershell
python model/baseline_relationship.py --city pune
python model/run_models.py --city pune
```

Replace `pune` with `london`, `new-york` or `athens` to build a different configured city. Outputs are written to that city's `data/cities/<slug>/outputs/` folder. The model layer reads the same city configuration as the pipeline; its metric projection is calculated from the city's centre rather than being fixed to Pune's UTM zone.

Core modules are heat model, greenness targets, forecast, need score and candidate sites. Financial sensitivity and exact portfolio optimisation run only when that city's assumptions pack has a validated finance model enabled. In this archive that is Pune only. Other city packs deliberately disable financial cost and carbon estimates rather than reusing INR-based or geographically inappropriate assumptions.

Models are trained and validated per city. Do not transfer Pune model weights, validation metrics or conclusions to London, New York or Athens. Complete the city-specific audit and release quality gate before presenting results.

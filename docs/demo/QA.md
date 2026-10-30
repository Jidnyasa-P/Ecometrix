# Likely questions, with honest answers

* **Why not deep learning?** The data are structured, spatial and moderate; planners need to see why a site was chosen. The ML model is used only if it beats a simple line under spatial cross-validation, and the audit page shows when it does not.
* **How accurate is the forecast?** See the backtest table: error on 2015 to 2020 when trained on 2000 to 2014, against "no change". The history is WorldPop's modelled series, and 2035 is a scenario.
* **Is the cooling real?** It is the heat model's association between greenness and satellite surface temperature across Pune, applied to a site once planting matures. It is not air temperature and not proof for a specific site.
* **Where do costs come from?** Sourced ranges (press-reported mini-forest quotes, PMC's own garden spending, NABARD and IEG discount rates). No Pune rate schedule was found. The assumptions register lists every value and which bounds are judgement.
* **Why no carbon for parks?** No Indian measurement of park carbon uptake was found; we do not guess.
* **What changes the ranking most?** The Evaluation page's sensitivity bars. The need-score weights are policy choices; the Priority page shows how much rankings move.
* **Is the optimiser really optimal?** Exact solver, proven equal to brute force on small cases; each solution reports its solver status and gap.
* **Does it scale to another city?** Change `config/pilot_pune.yaml` (and data sources); nothing else is Pune-specific. Not yet proven on a second city.
* **What is simulated and what is real?** Data layers are MEASURED or MODELLED from real data. Everything about plans is SIMULATED because nothing has been built.

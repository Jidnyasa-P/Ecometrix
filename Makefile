.PHONY: install data model api web test
CITY ?= pune
install:
	python -m pip install -r requirements.txt
	python -m pip check
	cd frontend && npm ci
# The selected city is built into its own data/cities/<slug>/ folder.
data:            ## build a city baseline (requires internet; set CITY=london, new-york or athens)
	PYTHONPATH=pipelines python -m ecometrix_pipeline.run --city $(CITY)
	python model/baseline_relationship.py --city $(CITY)
	python model/run_models.py --city $(CITY)
	PYTHONPATH=pipelines python -m ecometrix_pipeline.quality_gate --city $(CITY)
model:
	python model/run_models.py --city $(CITY)
api:
	python -m uvicorn app.main:app --app-dir backend --reload --port 8000
web:
	cd frontend && npm run dev
test:
	PYTHONPATH=pipelines python -m pytest pipelines/tests -q
	python -m pytest model/tests -q
	cd backend && python -m pytest -q
	cd frontend && npm run typecheck && npm test

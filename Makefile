.PHONY: install data model api web test
install:
	pip install -r pipelines/requirements.txt -r model/requirements.txt -r backend/requirements-dev.txt
	cd frontend && npm ci
data:            ## build the real baseline (needs internet; takes a while)
	PYTHONPATH=pipelines python -m ecometrix_pipeline.run
	python model/baseline_relationship.py
	python model/run_models.py
api:
	python -m uvicorn app.main:app --app-dir backend --reload --port 8000
web:
	cd frontend && npm run dev
test:
	PYTHONPATH=pipelines python -m pytest pipelines/tests -q
	python -m pytest model/tests -q
	cd backend && python -m pytest -q
	cd frontend && npm run typecheck && npm test

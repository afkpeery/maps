.PHONY: test backend frontend
backend:
	cd backend && uvicorn app:app --reload --host 127.0.0.1 --port 8000
frontend:
	cd frontend && npm run dev
test:
	cd backend && python -m pytest -q
	cd frontend && npm run build

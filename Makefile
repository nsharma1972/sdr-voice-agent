.PHONY: demo install dev refresh

demo:
	@bash scripts/start_demo.sh

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.main:app --reload --port 8000

refresh:
	curl -s -X POST http://localhost:8000/signals/refresh | python3 -m json.tool

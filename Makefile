.PHONY: bot worker qa

bot:
	docker compose up bot

worker:
	poetry run python -m arq melinoe.worker.WorkerSettings

qa:
	poetry run pre-commit run --all-files

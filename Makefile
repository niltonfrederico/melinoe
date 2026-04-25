.PHONY: bot worker qa

bot:
	docker compose up bot

worker:
	docker compose up worker

qa:
	poetry run pre-commit run --all-files

.PHONY: bot qa

bot:
	docker compose up bot

qa:
	poetry run pre-commit run --all-files

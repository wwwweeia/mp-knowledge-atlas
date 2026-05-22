.PHONY: migrate refresh build serve all test clean
SHELL := /bin/bash
PY := uv run python

migrate:
	$(PY) -m scripts.migrate_markdown --dir articles --db data/articles.db

refresh:
	$(PY) -m src.embed
	$(PY) -m src.cluster
	$(PY) -m src.name
	$(PY) -m src.network
	$(PY) -m src.publish

build:
	cd site && pnpm install && pnpm build

serve:
	cd site && pnpm dev

all: refresh build

test:
	uv run pytest

clean:
	rm -rf out site/.vitepress/dist site/.vitepress/cache

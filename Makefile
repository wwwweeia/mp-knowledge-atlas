.PHONY: ingest refresh rebuild build serve all test clean
SHELL := /bin/bash
PY := uv run python

WEMP_DB ?= /Users/wqw/Documents/idea_work/tools/we-mp-rss/data/we_mp_rss.db

ingest:
	$(PY) -m src.ingest --wemp $(WEMP_DB)

# 增量刷新：只处理新增/回填的文章，已处理的文章跳过
refresh:
	$(PY) -m src.ingest --wemp $(WEMP_DB)
	$(PY) -m src.clean
	$(PY) -m src.summarize
	$(PY) -m src.embed
	$(PY) -m src.cluster
	$(PY) -m src.network
	$(PY) -m src.publish

# 全量重跑：清空数据从头开始（耗时较长，首次或调试用）
rebuild: clean refresh

build:
	cd site && pnpm install && pnpm build

serve:
	cd site && pnpm dev

all: refresh build

test:
	uv run pytest

clean:
	rm -rf out data/articles.db data/chroma site/.vitepress/dist site/.vitepress/cache

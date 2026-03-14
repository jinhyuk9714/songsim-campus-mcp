.PHONY: install seed api mcp-http mcp-stdio test lint

install:
	uv sync --extra dev --extra mcp --extra scrape

seed:
	uv run songsim-seed-demo --force

api:
	uv run songsim-api

mcp-http:
	uv run songsim-mcp --transport streamable-http

mcp-stdio:
	uv run songsim-mcp --transport stdio

test:
	uv run pytest

lint:
	uv run ruff check .

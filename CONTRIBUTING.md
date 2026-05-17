# Contributing to pytest-test-observer

This document is for people modifying the plugin itself. For end-user docs see [`README.md`](./README.md).

N.B. The contributing guide is still in progress.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) ≥ 0.10
- Python ≥ 3.9
- Docker

## First-time setup

```bash
uv sync
uv run pytest -v
docker compose up -d
make smoke
```

To see the result, open Grafana on localhost: <http://localhost:3000/>

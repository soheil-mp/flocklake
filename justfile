# FlockLake task runner. Run `just` to list recipes.
# Install just: https://just.systems (or `uv tool install rust-just`).

set shell := ["bash", "-euo", "pipefail", "-c"]

# List the available recipes
default:
    @just --list --unsorted

# Install all packages and dev tools from the lockfile, and the git hooks
bootstrap:
    uv sync --all-packages --frozen
    uv run --frozen pre-commit install --install-hooks

# Run every pre-commit hook on the whole repository (lint, format, types, secrets)
lint:
    uv run --frozen pre-commit run --all-files

# Format Python code in place
fmt:
    uv run --frozen ruff check --fix
    uv run --frozen ruff format

# Type-check with mypy in strict mode
typecheck:
    uv run --frozen mypy

# Run the tests; extra arguments go to pytest (e.g. `just test -m unit -k physics`)
test *args:
    uv run --frozen pytest {{ args }}

# Run the tests with branch coverage and the 90 % gate
cov:
    uv run --frozen pytest --cov --cov-report=term-missing --cov-report=xml

# Everything CI checks, in the same order
check: lint test

# Query one night of real migration data from the public Aloft bucket (needs DuckDB)
example:
    duckdb < examples/night-traffic.sql

# Build the documentation site (milestone M0.11)
docs:
    @echo "The documentation site arrives with roadmap item M0.11." && exit 1

# Start the local platform (milestone M2)
up:
    @echo "The local platform arrives with roadmap milestone M2." && exit 1

# Stop the local platform (milestone M2)
down:
    @echo "The local platform arrives with roadmap milestone M2." && exit 1

# Remove caches and build output (keeps .venv)
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache .hypothesis .coverage coverage.xml htmlcov dist build

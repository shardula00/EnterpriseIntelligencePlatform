# data/

Local working area for datasets used during development.

- `raw/` — untouched source files (CSV/Excel/JSON). Never committed.
- `processed/` — cleaned/transformed outputs of the ingestion pipeline. Never committed.
- `interim/` — scratch/intermediate data. Never committed.

Real data files are excluded via [.gitignore](../.gitignore). Only small,
anonymized sample files (named `sample_*.csv`) are ever committed, and only
once ingestion work starts in Phase 2.

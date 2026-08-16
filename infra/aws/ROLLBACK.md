# Phase 13 — Rollback to local-only

Satisfies the Phase 13 Definition of Done: "rollback to local-only is
possible without data loss." Restores a production backup (see
`backup.sh`/`eip-backup.timer`, §7 of README.md) into your local
Docker-based dev environment (`infra/docker-compose.yml`).

## 1. Retrieve the latest backup from the instance

No SSH, no public port for this - use SSM Session Manager port
forwarding or `aws s3 cp` if you've additionally copied backups to S3
(not part of this phase's locked scope, see backup.sh's comments). The
simplest built-in path is an SSM Session Manager shell (`aws ssm
start-session --target <instance-id>`) plus any file-transfer approach
you're comfortable with (e.g. temporarily `aws s3 cp` the backup files to
a bucket you control, or `base64`+paste for small files) - deliberately
left as "however you prefer," since AWS doesn't provide a single built-in
`scp`-over-SSM primitive.

You're retrieving two files from `/opt/eip/backups/` on the instance,
both from the same timestamp:
- `db_<timestamp>.sql.gz`
- `appdata_<timestamp>.tar.gz`

## 2. Restore the database locally

With local Postgres already running (`docker compose up -d postgres` from
`infra/`):

```powershell
# From the directory containing the downloaded db_<timestamp>.sql.gz
gzip -dc db_<timestamp>.sql.gz | docker exec -i eip-postgres-1 psql -U eip_user -d eip_dev
```

This replaces data in the existing local `eip_dev` database with the
production dump's contents - back up your own local data first with the
same `pg_dump` approach if you want to keep both.

## 3. Restore the app data files locally

```powershell
tar -xzf appdata_<timestamp>.tar.gz -C E:\EnterpriseIntelligencePlatform\data
```

This puts the production `raw/uploads`, `raw/documents`, and
`ml_artifacts` back under the repo's local `data/` directory - the exact
path `infra/docker-compose.yml`'s backend service already bind-mounts, so
no other configuration change is needed.

## 4. Verify

```powershell
cd infra
docker compose up -d
```

Then check `http://localhost:8000/health` and log in - datasets, ML runs,
RAG documents, and decisions from the restored dump should all be
present, exactly as they were in production at backup time.

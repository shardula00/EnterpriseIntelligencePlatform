# Phase 13 — AWS deployment runbook

Deploys the same platform `infra/docker-compose.yml` runs locally to a
single EC2 instance, per the approved Phase 13 plan:
[EC2 t3.small](#3-launch-the-ec2-instance), self-hosted Postgres+pgvector
(no RDS), [SSM Parameter Store](#4-create-ssm-parameters) for secrets (no
`.env` in production), [SSM Session Manager](#3-launch-the-ec2-instance)
only (no SSH/port 22), [GitHub Actions + OIDC + ECR + SSM Run
Command](#6-github-repository-configuration) for deploys (manual
`workflow_dispatch` only), and [AWS Budgets](#8-aws-budgets-cost-alert)
for cost alerting. No Kubernetes/EKS, no RDS, no ALB.

**Nothing in this file has been run.** Every step below is a manual
action for you (or something I can execute only once you're ready and
have provided what's needed) - see the "Before you start" checklist and
each step's prerequisites. This is intentional per the approved plan:
_"Before creating any AWS resource, stop and tell me exactly what I need
to create/provide manually."_

## Before you start - what only you can provide

I have no AWS account access. None of the values below are guessed or
invented - they're the literal blanks in this runbook:

| # | What | Used in |
|---|---|---|
| 1 | AWS account access (console or CLI credentials configured on whatever machine runs these commands) | every step |
| 2 | Your AWS Account ID | replaces every `<ACCOUNT_ID>` in `infra/aws/iam/*.json` and this file |
| 3 | Confirmation of `us-east-1` as the region, or a different one | every AWS CLI command below |
| 4 | A real domain name you own and can add DNS records for | §9 - **HTTPS setup is on hold without this**, per the approved plan |
| 5 | Your monthly AWS Budget limit (a dollar figure) | `infra/aws/budget.json` - currently a placeholder |
| 6 | The email address for AWS Budgets alerts | `infra/aws/budget-notifications.json` - currently a placeholder |
| 7 | This GitHub repo's `<GITHUB_ORG>/<GITHUB_REPO>` | `infra/aws/iam/github-oidc-trust-policy.json` |
| 8 | A real value for `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, and `BOOTSTRAP_ADMIN_PASSWORD` (generate your own, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`) | §4 - **entered directly by you** into the `aws ssm put-parameter` commands or the console; never shared in chat, never committed |

Nothing below asks you to paste a password, key, or secret into this chat
- per the approved plan, I never request or store one. Every command that
needs a real secret value is written for *you* to run yourself, with the
value substituted locally on your machine.

## 1. Create the IAM roles

Two roles, two purposes - the EC2 instance's own role (reads SSM
parameters, pulls from ECR), and a separate role GitHub Actions assumes
via OIDC (pushes to ECR, triggers the deploy on the instance). Neither
role has standing AWS access keys.

```powershell
# Replace <ACCOUNT_ID> everywhere first, or use `aws sts get-caller-identity`
# to look it up.

# --- EC2 instance role ---
aws iam create-role `
  --role-name eip-ec2-instance-role `
  --assume-role-policy-document file://infra/aws/iam/ec2-instance-role-trust-policy.json

aws iam put-role-policy `
  --role-name eip-ec2-instance-role `
  --policy-name eip-ec2-instance-policy `
  --policy-document file://infra/aws/iam/ec2-instance-role-policy.json

# AWS-managed policy that makes SSM Session Manager (our SSH replacement)
# work - not reinvented here.
aws iam attach-role-policy `
  --role-name eip-ec2-instance-role `
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

aws iam create-instance-profile --instance-profile-name eip-ec2-instance-profile
aws iam add-role-to-instance-profile `
  --instance-profile-name eip-ec2-instance-profile `
  --role-name eip-ec2-instance-role

# --- GitHub Actions OIDC provider (one per AWS account, skip if you
#     already have one for this account) ---
aws iam create-open-id-connect-provider `
  --url https://token.actions.githubusercontent.com `
  --client-id-list sts.amazonaws.com `
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# --- GitHub deploy role (edit github-oidc-trust-policy.json's
#     <GITHUB_ORG>/<GITHUB_REPO> first) ---
aws iam create-role `
  --role-name eip-github-deploy-role `
  --assume-role-policy-document file://infra/aws/iam/github-oidc-trust-policy.json

aws iam put-role-policy `
  --role-name eip-github-deploy-role `
  --policy-name eip-github-deploy-policy `
  --policy-document file://infra/aws/iam/github-deploy-role-policy.json
```

## 2. Create the ECR repositories

```powershell
aws ecr create-repository --repository-name eip-backend --region us-east-1
aws ecr create-repository --repository-name eip-frontend --region us-east-1

# Optional but recommended: expire untagged images after 14 days so old
# build layers don't quietly accumulate storage cost.
aws ecr put-lifecycle-policy --repository-name eip-backend --region us-east-1 --lifecycle-policy-text '{"rules":[{"rulePriority":1,"selection":{"tagStatus":"untagged","countType":"sinceImagePushed","countUnit":"days","countNumber":14},"action":{"type":"expire"}}]}'
aws ecr put-lifecycle-policy --repository-name eip-frontend --region us-east-1 --lifecycle-policy-text '{"rules":[{"rulePriority":1,"selection":{"tagStatus":"untagged","countType":"sinceImagePushed","countUnit":"days","countNumber":14},"action":{"type":"expire"}}]}'
```

## 3. Launch the EC2 instance

- AMI: Amazon Linux 2023 (has `dnf`, Docker available via `dnf install docker`).
- Instance type: `t3.small` (see the approved plan for the cost comparison against `t3.micro`).
- IAM instance profile: `eip-ec2-instance-profile` (from step 1).
- Storage: one gp3 root volume, 30 GiB.
- **Security group**: inbound `80/tcp` and `443/tcp` from `0.0.0.0/0` only. **No inbound 22/tcp** - all shell access is via SSM Session Manager (`aws ssm start-session --target <instance-id>`), which needs no inbound port at all (only outbound HTTPS, which the default security group egress rule already allows).
- Allocate and associate an **Elastic IP** so the address is stable across stops/restarts.
- User data (installs Docker + Compose plugin, creates the persistent directories):
  ```bash
  #!/bin/bash
  dnf install -y docker
  systemctl enable --now docker
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  mkdir -p /opt/eip/data/postgres /opt/eip/data/app /opt/eip/data/caddy /opt/eip/backups /opt/eip/caddy_config
  ```

Once the instance is running, copy the deployment files onto it (via SSM
Session Manager + `aws s3 cp`, or by cloning this repo on the instance -
either way, only the `infra/aws/` contents are actually needed there):
`docker-compose.prod.yml`, `Caddyfile`, `fetch-secrets.sh`, `backup.sh`,
`eip-backup.service`, `eip-backup.timer` → all into `/opt/eip/`.

## 4. Create SSM parameters

Run these yourself, substituting your own values for every `<...>` -
these are never typed into this chat:

```powershell
aws ssm put-parameter --name /eip/prod/postgres_password --type SecureString --value "<A REAL GENERATED PASSWORD>"
aws ssm put-parameter --name /eip/prod/jwt_secret_key --type SecureString --value "<A REAL GENERATED SECRET>"
aws ssm put-parameter --name /eip/prod/bootstrap_admin_email --type SecureString --value "<YOUR ADMIN EMAIL>"
aws ssm put-parameter --name /eip/prod/bootstrap_admin_password --type SecureString --value "<A REAL GENERATED PASSWORD>"
# CORS_ALLOW_ORIGINS: leave as the localhost placeholder until you have a
# real domain (see §9) - do not invent one.
aws ssm put-parameter --name /eip/prod/cors_allow_origins --type SecureString --value '["https://REPLACE_WITH_YOUR_DOMAIN"]'
# Not a secret (it's just this account's ECR hostname), stored alongside
# the others anyway so fetch-secrets.sh only needs one mechanism for
# everything docker-compose.prod.yml's ${...} interpolation needs.
aws ssm put-parameter --name /eip/prod/ecr_registry --type String --value "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com"
```

Verify: `./infra/aws/fetch-secrets.sh` (run on the instance) should
produce a `.env.prod` with one line per parameter above - see that
script's comments for exactly how it maps SSM names to env var names.

## 5. First deploy (manual, before CI/CD exists)

```bash
cd /opt/eip
./fetch-secrets.sh
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

At this point the app is reachable over plain HTTP by Elastic IP
(`http://<elastic-ip>` won't work yet either, actually - see §9: Caddy is
the only service with a published port, and it won't start cleanly
without real domains in the Caddyfile). Until a domain exists, temporarily
comment out the `caddy` service in `docker-compose.prod.yml` and publish
`frontend`'s port directly (`"80:80"`) for a plain-HTTP smoke check - this
is a deliberate stopgap, not the intended end state.

## 6. GitHub repository configuration

Repository **Variables** (not secrets - none of these are credentials):

| Name | Value |
|---|---|
| `GITHUB_DEPLOY_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/eip-github-deploy-role` |
| `EC2_INSTANCE_ID` | the instance ID from step 3 |
| `PROD_APP_URL` | `https://app.<your domain>` (leave unset/blank until §9) |
| `PROD_API_BASE_URL` | `https://api.<your domain>` (leave unset/blank until §9) |

`.github/workflows/deploy.yml` will fail cleanly (not silently) on the
frontend build step if `PROD_API_BASE_URL` isn't set, and on the smoke
test step if `PROD_APP_URL` isn't set - both deliberately have no default,
so a run can't accidentally ship a bad URL baked into the frontend bundle.

## 7. Backup timer

On the instance:

```bash
sudo cp /opt/eip/eip-backup.service /opt/eip/eip-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eip-backup.timer
```

See [ROLLBACK.md](ROLLBACK.md) for what these backups are for and how to
restore from one.

## 8. AWS Budgets (cost alert)

`infra/aws/budget.json` and `infra/aws/budget-notifications.json` are
placeholders - **do not run the command below until you've replaced
`REPLACE_WITH_YOUR_MONTHLY_LIMIT_USD` with your real limit and
`REPLACE_WITH_YOUR_EMAIL` with your real address**, per the approved plan.

```powershell
aws budgets create-budget `
  --account-id <ACCOUNT_ID> `
  --budget file://infra/aws/budget.json `
  --notifications-with-subscribers file://infra/aws/budget-notifications.json
```

## 9. Domain and HTTPS

**On hold until you have a domain**, per the approved plan
(_"stop before configuring HTTPS if I don't yet have a domain. Do not
invent a domain."_). When you do:

1. Add two DNS `A` records at your domain's registrar/DNS provider,
   both pointing at the instance's Elastic IP: `app.<domain>` and
   `api.<domain>`.
2. Replace both `REPLACE_WITH_YOUR_DOMAIN` placeholders in
   `infra/aws/Caddyfile` with your real domain.
3. Update the `/eip/prod/cors_allow_origins` SSM parameter (§4) to your
   real `https://app.<domain>` origin.
4. Set `PROD_APP_URL`/`PROD_API_BASE_URL` (§6) to the real HTTPS URLs.
5. Re-run the deploy - Caddy will automatically obtain Let's Encrypt
   certificates for both domains on first start (requires port 80 to be
   reachable for the ACME HTTP-01 challenge, which the security group
   already allows).

## 10. Running a deploy

GitHub → Actions → **deploy** → "Run workflow" → type `deploy` in the
confirmation input. The workflow will refuse to do anything (fails at the
very first step) unless that input is exactly `deploy` - see
`.github/workflows/deploy.yml`.

## 11. Troubleshooting / ad-hoc access

No SSH. For a shell on the instance:

```powershell
aws ssm start-session --target <instance-id>
```

For ad-hoc `psql` access without publishing Postgres's port publicly, use
SSM port forwarding from your own machine:

```powershell
aws ssm start-session --target <instance-id> `
  --document-name AWS-StartPortForwardingSession `
  --parameters '{"portNumber":["5432"],"localPortNumber":["5432"]}'
```

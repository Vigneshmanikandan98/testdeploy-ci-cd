# Allocator sample: Docker + GitHub Actions + Azure Container Apps

Same shape as the real Allocator (React `frontend-v2` + FastAPI `backend-v2`, one container),
with no Oracle dependency, so you can test the whole deployment path on a personal laptop.

```
allocator-sample/
├── frontend-v2/                 React (Vite). Calls the API with relative paths (/api/...)
├── backend-v2/
│   ├── app/main.py              /health, /api/info, /api/projects, then the React catch-all
│   ├── requirements.txt
│   └── .env.example
├── Dockerfile                   Stage 1 builds React, stage 2 runs FastAPI + the build
├── .dockerignore
└── .github/workflows/deploy.yml Push to main -> build -> ACR -> Container App
```

## Test 1: run without Docker (optional sanity check)

Two terminals. No build step is needed in this mode.

```bash
cd frontend-v2 && npm install && npm run dev          # terminal 1
cd backend-v2 && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000   # terminal 2
```

Open **http://localhost:5173** (Vite serves React and forwards /api to FastAPI).
Opening http://localhost:8000 in this mode shows "Frontend not built yet". That's expected:
nothing has built React. Docker (Test 2) does that build for you.

Stop both terminals before Test 2 so port 8000 is free.

## Test 2: run in Docker on your laptop

Install Docker Desktop (free for personal use), then from the repo root (the folder with `Dockerfile`).
You do not run `npm run build` yourself; the Dockerfile does it (look for `RUN npm run build` in the output):

```bash
docker build -t allocator .
docker run -p 8000:8000 -e APP_ENV=docker -e DB_PASSWORD=test allocator
```

Open http://localhost:8000. You should see Environment = docker and Secret configured = Yes.

## Test 3: deploy to Azure

Order matters: the Container App is created from YOUR image (port 8000) after the
pipeline has pushed it once. No placeholder image, so no port switch later.

### 3a. Create the registry and environment (Azure portal -> Cloud Shell, Bash)

```bash
RG=rg-allocator-test
LOC=eastus
ACR=allocatoracr$RANDOM          # must be globally unique; WRITE DOWN the printed name
APP=allocator
ENV=allocator-env
echo $ACR

az provider register -n Microsoft.ContainerRegistry --wait
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.OperationalInsights --wait

az group create -n $RG -l $LOC
az acr create -n $ACR -g $RG --sku Basic
az containerapp env create -n $ENV -g $RG -l $LOC
```

If Cloud Shell restarts, set the variables again with your real name (ACR=allocatoracr12345),
not $RANDOM. Cloud Shell disconnects after ~20 idle minutes; a frozen screen is usually that.

### 3b. Let GitHub log in to Azure

Run one command at a time. Build the exact subject GitHub will send (new repos include
numeric owner/repo IDs). For a public repo:

```bash
OWNER=<GITHUB_USER>
REPO=<REPO>
INFO=$(curl -s https://api.github.com/repos/$OWNER/$REPO)
SUBJECT="repo:$OWNER@$(echo $INFO | jq -r .owner.id)/$REPO@$(echo $INFO | jq -r .id):ref:refs/heads/main"
echo $SUBJECT
```

(Private repo: on your laptop run
`gh api repos/OWNER/REPO --jq '"repo:\(.owner.login)@\(.owner.id)/\(.name)@\(.id):ref:refs/heads/main"'`
and set SUBJECT to the printed value.)

```bash
APP_ID=$(az ad app create --display-name allocator-github --query appId -o tsv)
echo $APP_ID                     # must print an ID before you continue
az ad sp create --id $APP_ID
SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)

az role assignment create --assignee $APP_ID --role Contributor --scope /subscriptions/$SUB/resourceGroups/$RG

az ad app federated-credential create --id $APP_ID --parameters "{
  \"name\": \"github-main\",
  \"issuer\": \"https://token.actions.githubusercontent.com\",
  \"subject\": \"$SUBJECT\",
  \"audiences\": [\"api://AzureADTokenExchange\"]
}"

echo "AZURE_CLIENT_ID=$APP_ID"; echo "AZURE_TENANT_ID=$TENANT"; echo "AZURE_SUBSCRIPTION_ID=$SUB"
```

If `az ad app create` says "Timeout waiting for token", run
`az login --scope "https://graph.microsoft.com//.default"` and retry.
If the role assignment says the principal doesn't exist, wait 30 seconds and rerun it.

### 3c. Configure the GitHub repo

Repo -> Settings -> Secrets and variables -> Actions:

| Tab | Name | Value |
|---|---|---|
| Secrets | AZURE_CLIENT_ID | from 3b |
| Secrets | AZURE_TENANT_ID | from 3b |
| Secrets | AZURE_SUBSCRIPTION_ID | from 3b |
| Variables | ACR_NAME | your registry name |
| Variables | CONTAINER_APP_NAME | allocator |
| Variables | RESOURCE_GROUP | rg-allocator-test |

### 3d. First pipeline run: pushes the image

Push to `main` (or Actions -> Deploy Allocator -> Run workflow). It builds and pushes the
image, then stops with a warning that the Container App doesn't exist yet. That's expected.

### 3e. Create the Container App once, from that image

```bash
TAG=$(az acr repository show-tags -n $ACR --repository allocator --orderby time_desc --top 1 -o tsv)
echo $TAG

az containerapp create -n $APP -g $RG --environment $ENV \
  --image $ACR.azurecr.io/allocator:$TAG \
  --ingress external --target-port 8000 \
  --min-replicas 0 --max-replicas 1 \
  --registry-server $ACR.azurecr.io --registry-identity system

az containerapp show -n $APP -g $RG --query properties.configuration.ingress.fqdn -o tsv
```

Open the printed URL. This takes 2-4 minutes. `--min-replicas 0` keeps the trial cheap
(the first request after idle takes a few seconds). Use 1 for the real app.

### 3f. Every deploy from now on

Push to `main`. The workflow builds (cached, ~1 min), updates the image (~1-3 min), and
checks `/health`. Total is typically under 5 minutes. If anything fails, the Diagnostics
step prints revision health and system logs, so you see why instead of a spinner.

### 3g. Test a secret (mirrors the Oracle password)

```bash
az containerapp secret set -n $APP -g $RG --secrets db-password=supersecret
az containerapp update -n $APP -g $RG --set-env-vars APP_ENV=azure DB_PASSWORD=secretref:db-password
```

Refresh: Environment = azure, Secret configured = Yes.

### 3h. Prove CI/CD

Change a project name in `backend-v2/app/main.py`, push to main, watch it go live.

## CI/CD: how branches and pull requests work

| Event | Workflow | What happens | Touches Azure? |
|---|---|---|---|
| Push to a feature branch | none | Nothing | No |
| Open or update a PR into `main` | `ci.yml` | Backend tests, frontend build, Docker build (no push) | No |
| Merge the PR (= push to `main`) | `deploy.yml` | Runs `ci.yml` again on the merged code, then build, push, deploy, health check | Yes |
| Actions -> Run workflow | `deploy.yml` | Same as a merge, on demand | Yes |

CI answers "is this change safe to merge?" CD answers "ship what's on main."

### Branch protection (one time, repo admin)

Settings -> Branches -> Add rule for `main`:
- Require a pull request before merging (1 approval)
- Require status checks to pass: select `backend`, `frontend`, `docker` (they appear after CI has run once)
- Require branches to be up to date before merging

Now no one can push straight to production, and a red CI blocks the merge button.

### Run tests locally

```bash
cd backend-v2
pip install -r requirements-dev.txt
python -m pytest -q
```

## Clean up (avoid trial charges)

```bash
az group delete -n rg-allocator-test --yes
az ad app delete --id $APP_ID
```

## What carries over to the real Allocator

Same Dockerfile shape, same workflow file. Differences: Oracle connection env vars and secrets,
min replicas 1, Entra ID sign-in (Container App -> Authentication), and the work Azure account.

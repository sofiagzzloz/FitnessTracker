# Fitness Tracker
A full-stack fitness tracker web application built with **FastAPI**, **SQLModel/SQLite**, and a simple **JS/HTML/CSS frontend**.  
It supports authentication, exercise/workout/session management, and external exercise imports from the **WGER API**.

## Features

- **Authentication**
  - Register, login, logout with JWT + HttpOnly cookies
  - Session-based protection for all main app pages
- **Exercises**
  - Add custom exercises (per-user scoped)
  - Import exercises from WGER external API
  - Delete exercises (with usage validation)
  - List exercises filtered by category or name
- **Workouts**
  - Create workout templates
  - Add/remove items (exercises) with planned sets/reps
  - View muscle distribution summaries
- **Sessions**
  - Log training sessions (linked to templates or standalone)
  - Track "planned" vs. "actual" execution
  - View + edit session items
- **Frontend**
  - Vanilla JS (auth.js, exercises.js, workouts.js, sessions.js)
  - Cookie-aware fetch helpers
  - Heatmap overlays (muscle group visualization)
- **Database**
  - User-specific data isolation (`user_id` foreign keys on exercises, workouts, sessions)
  - SQLite for local development, PostgreSQL (Azure Database for PostgreSQL Flexible Server) for deployment
- **Testing**
  - Pytest suite with coverage of authentication, exercises, workouts, and sessions flows


## Project Structure
```bash
.
├── app
│   ├── __init__.py
│   ├── auth.py
│   ├── db.py
│   ├── main.py
│   ├── models.py
│   ├── routers
│   │   ├── auth.py
│   │   ├── exercises.py
│   │   ├── external.py
│   │   ├── sessions.py
│   │   └── workouts.py
│   ├── schemas.py
│   ├── server.py
│   └── services
│       ├── adapters
│       │   ├── __init__.py
│       │   └── wger.py
│       ├── common.py
│       ├── exercises_service.py
│       ├── sessions_service.py
│       └── workouts_service.py
├── docker
│   ├── backend.Dockerfile
│   ├── db-init.sql
│   └── db.Dockerfile
├── frontend.Dockerfile
├── monitoring
│   └── prometheus.yml
├── reports
│   ├── coverage.xml
│   └── TEST_REPORT.md
├── static
│   ├── auth.js
│   ├── config.js
│   ├── exercises.js
│   ├── heatmap.js
│   ├── sessions.js
│   ├── styles.css
│   ├── workouts.js
│   └── img/
├── templates
│   ├── exercises.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── sessions.html
│   └── workouts.html
├── tests
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_exercises.py
│   ├── test_external.py
│   ├── test_health_and_metrics.py
│   └── test_workouts_and_sessions.py
├── coverage.xml
├── fitness.db
├── nginx.conf
├── README.md
├── requirements.txt
├── test-ci.db
└── .env.example
```

## Setup Instructions

### 1. Clone repository
```bash
git clone https://github.com/yourusername/fitness_tracker.git
cd fitness_tracker
```
### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows
```
### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
### 4. Environment variables
Copy .env.example and turn it into .env, then edit as needed. Key values:
- `DATABASE_URL=sqlite:///./fitness.db` → local default (set to your managed Postgres/SQL when deploying)
- `JWT_SECRET`, `JWT_ALG`, `JWT_TTL_SECONDS`

### 5. Run development Server
```bash
uvicorn app.main:app --reload
```

## Testing 
Run all tests:
```bash
pytest -q
```
Generate coverage (required for CI) and refresh the committed report:
```bash
python -m pytest --cov=app --cov-config=.coveragerc --cov-report=term-missing --cov-report=xml
cp coverage.xml reports/coverage.xml
```
The latest run summary lives in `reports/TEST_REPORT.md`.
Current test coverage:
- Authentication: register, login, logout, /me, page access control
- Exercises: create, import, list, delete, filter
- Workouts: templates, items, muscle summaries
- Sessions: create, list, update, delete

## Docker Build & Deployment

### Frontend (Nginx) Build with Cache Busting

When building the frontend Docker image, use the `CACHE_BUST` build argument to force Docker to rebuild static file layers:

```bash
# Build with cache busting (use timestamp or version number)
docker buildx build \
  --platform linux/amd64 \
  --build-arg CACHE_BUST=$(date +%s) \
  -f frontend.Dockerfile \
  -t <your-acr>.azurecr.io/fitness-frontend:latest \
  --push \
  .

# Or use a version number
docker buildx build \
  --platform linux/amd64 \
  --build-arg CACHE_BUST=dev12 \
  -f frontend.Dockerfile \
  -t <your-acr>.azurecr.io/fitness-frontend:latest \
  --push \
  .
```

**Important**: Always increment the `CACHE_BUST` value when static files change. This ensures Docker doesn't use cached layers for the `COPY static` command.

### Why Cache Busting is Needed

Docker caches layers based on file checksums. If Docker thinks files haven't changed, it reuses cached layers even after you've modified files. The `CACHE_BUST` build argument invalidates the cache, forcing Docker to rebuild the static file layers.

## Azure Deployment & CI/CD

### App Service container deployment
1. Build the backend image with `docker/backend.Dockerfile` (now running `python -m app.server`).
2. Create an Azure Web App for Containers (Linux) and point it at the image hosted in GHCR (`ghcr.io/<your-account>/fitness-tracker:latest`).
3. In the Web App configuration add required settings (at minimum `DATABASE_URL`, JWT values, and any API keys).
4. Use Azure Database for PostgreSQL Flexible Server (or another managed DB) and update `DATABASE_URL` accordingly.

### Azure Database for PostgreSQL setup
1. Create a flexible server (single zone) in the same region as the App Service:
  ```bash
  az postgres flexible-server create \
    --resource-group <rg-name> \
    --name <server-name> \
    --location <region> \
    --sku-name Standard_D2ds_v5 \
    --tier GeneralPurpose \
    --version 16 \
    --admin-user fitness \
    --admin-password <StrongPassword>
  ```
2. Configure a firewall rule or VNet integration so the App Service can reach the database (if both are in the same VNet, enable private access; otherwise allow the outbound IPs of the Web App).
3. Create the database schema (the FastAPI app will auto-create tables on startup via SQLModel, so no migrations are needed yet).
4. Build the SQLAlchemy connection string using the psycopg driver and enforced TLS:
  ```
  postgresql+psycopg://fitness:<password>@<server-name>.postgres.database.azure.com:5432/<database>?sslmode=require
  ```
5. Store this string as `DATABASE_URL` in both the Web App configuration and the GitHub repository secrets (for any workflows that need DB access, e.g., migrations).

### GitHub Actions workflows
- `.github/workflows/ci.yml` runs flake8 + pytest on every push/PR (branches `main` + `azure`). It sets `DATABASE_URL=sqlite:///./test-ci.db` so tests use an ephemeral SQLite file.
- `.github/workflows/deploy.yml` builds the Docker image, pushes it to GitHub Container Registry, and deploys it to Azure App Service when commits land on `main`.

Required GitHub secrets for deployment:
- `AZURE_CREDENTIALS` → output of `az ad sp create-for-rbac ... --sdk-auth` with access to the target subscription/resource group.
- `AZURE_WEBAPP_NAME` → the name of your Azure Web App for Containers.

Optional secrets/env vars:
- `DATABASE_URL` if you want to override the default inside Actions jobs.
- `UVICORN_WORKERS`, `UVICORN_LOG_LEVEL` for custom container runtime tuning.



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
  - SQLite in development, easily swappable to PostgreSQL
- **Testing**
  - Pytest suite with coverage of authentication, exercises, workouts, and sessions flows


## Project Structure
```bash
fitness_tracker/
├── app/
│   ├── main.py                    
│   ├── auth.py                    
│   ├── db.py                      
│   ├── models.py                  
│   ├── schemas.py                 
│   ├── routers/
│   │   ├── auth.py                 
│   │   ├── exercises.py            
│   │   ├── workouts.py             
│   │   ├── sessions.py            
│   │   └── external.py            
│   └── services/
│       └── adapters/
│           ├── __init__.py
│           └── wger.py            
├── static/
│   ├── styles.css                  
│   ├── auth.js                    
│   ├── exercises.js                
│   ├── workouts.js                
│   ├── sessions.js                
│   └── heatmap.js                  
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── index.html                  
│   ├── exercises.html
│   ├── workouts.html
│   └── sessions.html
├── tests/
│   ├── conftest.py                 
│   ├── test_auth.py                
│   ├── test_exercises.py          
│   └── test_workouts_and_sessions.py  
├── requirements.txt
├── .env.example                    
└── README.md
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
Copy .env.example and turn it into .env, then edit as needed 

### 5. Run development Server
```bash
uvicorn app.main:app --reload
```

## Testing 
Run all tests:
```bash
pytest -q
```
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

## Future Work
For Assignment 2
- Switch from SQLite → PostgreSQL for deployment
- Dockerize services (FastAPI app, DB)
- CI/CD integration (GitHub Actions)


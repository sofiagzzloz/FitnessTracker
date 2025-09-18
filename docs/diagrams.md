## System Architecture
::: mermaid
flowchart LR
    subgraph Client["UI Layer (Browser)"]
      UI[Simple HTML + JS<br/>• Create workout<br/>• Filters<br/>• Delete]
    end

    subgraph API["FastAPI Backend"]
      R1[/Routers: /workouts, /exercises/]
      V1[[Pydantic Schemas<br/>• WorkoutCreate/Read/Update<br/>• ExerciseCreate/Read/Update]]
      BL[(Business Logic<br/>• Validation<br/>• Enrichment: exercise_name/category)]
      DBI[[SQLModel / SQLAlchemy]]
    end

    subgraph Data["Data Layer"]
      DB[(SQLite file: app.db)]
    end

    UI -->|HTTP JSON| R1
    R1 --> V1 --> BL --> DBI --> DB

    %% Use a helper node for the note (flowcharts don't support 'note right of')
    NOTE_DB["Swap SQLite→Postgres later by<br/>changing DATABASE_URL"]
    DBI -.-> NOTE_DB
:::

## Data Flow (Current)

::: mermaid
sequenceDiagram
    %% Participants, grouped for clarity
    participant U as User (Browser)
    participant UI as UI (app.js)

    box Aqua Backend (FastAPI & DB)
        participant R as Router (FastAPI)
        participant S as Schemas (Pydantic)
        participant M as Models (SQLModel)
    end

    participant D as SQLite (app.db)
    
    %% ----- FLOW 1: Submit Workout -----
    Note over U,UI: User submits workout form.
    U->>UI: Fill form (date, exercise, sets…)

    UI->>R: POST /workouts {json}
    Note left of R: Validate data
    R->>S: Validate WorkoutCreate

    alt Validation passes
        S-->>R: Valid payload
        R->>M: session.add(Workout) + commit
        M->>D: INSERT INTO workout(…)
        D-->>M: id generated
        M-->>R: Workout row
        R->>M: Lookup Exercise by exercise_id
        M-->>R: {exercise_name}
        R-->>UI: 201 Created, WorkoutRead
    else Validation fails
        S-->>R: 422 Unprocessable Entity
        R-->>UI: 422 Validation error
    end

    %% ----- FLOW 2: Filter Workouts -----
    Note over U,UI: User filters workouts
    U->>UI: Filter workouts

    UI->>R: GET /workouts?filters
    R->>M: SELECT ... WHERE ...
    M->>D: Read rows
    D-->>M: result set
    M-->>R: list of Workouts
    R-->>UI: 200 [WorkoutRead…]
:::


## Data Flow (Final)
::: mermaid
sequenceDiagram
    autonumber
    box UserLayer #fdf5ff
    participant U as User (Browser)
    end

    box UILayer #e6f7ff
    participant UI as UI (app.js)
    end

    box Backend #e6f9ff
    participant R as Router (FastAPI)
    participant S as Schemas (Pydantic)
    participant M as Models (SQLModel)
    end

    box DBLayer #f0f0ff
    participant D as SQLite (app.db)
    end

    %% === Workflow submission ===
    U->>UI: Fill form (date, exercise, sets…)
    note right of U: User submits workout form
    UI->>R: POST /workouts {json}
    note right of R: Validate data
    R->>S: Validate WorkoutCreate
    S-->>R: Valid payload or 422
    alt Validation passes
        R->>M: session.add(Workout) + commit
        M->>D: INSERT INTO workout(…)
        D-->>M: id generated
        M-->>R: Workout row
        R->>M: Lookup Exercise by exercise_id
        R-->>UI: 201 Created, WorkoutRead
    else Validation fails
        R-->>UI: 422 Validation Error
    end

    %% === Filtering workouts ===
    U->>UI: Filter workouts
    note right of U: User filters workouts
    UI->>R: GET /workouts?filters
    R->>M: SELECT … WHERE …
    M->>D: Read rows
    D-->>M: result set
    M-->>R: list of Workouts
    R-->>UI: 200 [WorkoutRead…]

    %% === Planned v2 (sessions) ===
    alt Planned v2 — Session Builder
        U->>UI: Create Session (date, notes)
        UI->>R: POST /sessions {json}
        R->>M: session.add(WorkoutSession)
        M->>D: INSERT INTO workout_session(…)

        UI->>R: POST /sessions/{id}/items {exercise_id}
        R->>M: session.add(WorkoutItem)
        M->>D: INSERT INTO workout_item(…)

        UI->>R: POST /sessions/{id}/items/{item_id}/sets {reps, weight}
        R->>M: session.add(SetEntry)
        M->>D: INSERT INTO set_entry(…)
    end
:::

## Class Diagram
::: mermaid 
classDiagram
%% ---------- Classes ----------
class Exercise {
  <<current>>
  +int id
  +str name
  +str category
  +str default_unit
  +str tutorial_url?
  +str primary_muscle?
  +str secondary_muscles?
  +datetime created_at?
  +datetime updated_at?
}

class Workout {
  <<current>>
  +int id
  +date date
  +int exercise_id
  +int sets?
  +int reps?
  +float weight_kg?
  +float distance_km?
  +str notes?
  +datetime created_at
  +datetime updated_at
}

class WorkoutSession {
  <<planned>>
  +int id
  +date date
  +str title?
  +str notes?
  +datetime created_at
  +datetime updated_at
}

class WorkoutItem {
  <<planned>>
  +int id
  +int session_id
  +int exercise_id
  +str notes?
  +int order_index?
  +datetime created_at
  +datetime updated_at
}

class SetEntry {
  <<planned>>
  +int id
  +int item_id
  +int set_number
  +int reps?
  +float weight_kg?
  +float distance_km?
  +float duration_min?
  +datetime created_at
  +datetime updated_at
}

%% ---------- Relationships ----------
Exercise "1" --> "*" Workout : exercise_id
WorkoutSession "1" --> "*" WorkoutItem : contains
Exercise "1" --> "*" WorkoutItem : exercise_id
WorkoutItem "1" --> "*" SetEntry : has
:::

## ER Diagram
::: mermaid
erDiagram
    %% ===== V1 (kept for compatibility) =====
    EXERCISE ||--o{ WORKOUT : "used by (v1)"
    EXERCISE {
      int id PK
      string name
      string category
      string default_unit
      string tutorial_url  "optional"
      string primary_muscle  "optional"
      string secondary_muscles  "CSV or JSON, optional"
    }
    WORKOUT {
      int id PK
      date date
      int exercise_id FK
      int sets           "nullable"
      int reps           "nullable"
      float weight_kg    "nullable"
      float distance_km  "nullable"
      string notes       "nullable"
      datetime created_at
      datetime updated_at
    }

    %% ===== V2 (sessions with multiple exercises) =====
    WORKOUT_SESSION ||--o{ WORKOUT_ITEM : "contains"
    WORKOUT_ITEM ||--o{ SET_ENTRY : "has"
    EXERCISE ||--o{ WORKOUT_ITEM : "uses (v2)"

    WORKOUT_SESSION {
      int id PK
      date date
      string title        "optional, e.g., 'Leg Day'"
      string notes        "optional"
      datetime created_at
      datetime updated_at
    }

    WORKOUT_ITEM {
      int id PK
      int session_id FK
      int exercise_id FK
      string notes        "optional"
      int order_index     "for UI ordering"
      datetime created_at
      datetime updated_at
    }

    SET_ENTRY {
      int id PK
      int item_id FK
      int set_number      "1..N"
      int reps            "nullable"
      float weight_kg     "nullable"
      float distance_km   "nullable"
      float duration_min  "nullable, for cardio"
      datetime created_at
      datetime updated_at
    }
:::

## System Interfaces
::: mermaid
flowchart TB
    subgraph Client
      B[Browser UI]
    end

    subgraph FastAPI["FastAPI"]
      E1["GET, POST /exercises"]
      E2["GET, PUT, DELETE /exercises/{id}"]
      W1["GET, POST /workouts"]
      W2["GET, PUT, DELETE /workouts/{id}"]
      W3["GET /workouts/stats"]
      %% Planned v2
      S1["GET, POST /sessions"]
      S2["GET /sessions/{id}"]
      I1["POST, DELETE /sessions/{id}/items"]
    end

    subgraph Storage["Persistence"]
      DB[(SQLite app.db)]
    end

    %% Client calls to endpoints
    B --> E1
    B --> E2
    B --> W1
    B --> W2
    B --> W3
    B --> S1
    B --> S2
    B --> I1

    %% Endpoints talk to the database
    E1 --> DB
    E2 --> DB
    W1 --> DB
    W2 --> DB
    W3 --> DB
    S1 --> DB
    S2 --> DB
    I1 --> DB
:::
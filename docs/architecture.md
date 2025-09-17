## Schemas
CREATE TABLE workout (
  id INTEGER PRIMARY KEY,
  date DATE NOT NULL,
  exercise TEXT NOT NULL,
  sets INTEGER,
  reps INTEGER,
  weight_kg REAL,
  distance_km REAL,
  notes TEXT
);

CREATE TABLE exercise (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT,
  default_unit TEXT
);
CREATE INDEX ix_exercise_name ON exercise (name);


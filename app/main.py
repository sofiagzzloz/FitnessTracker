from fastapi import FastAPI

app = FastAPI(title= "Fitness Tracker")

@app.get("/")
def read_root():
    return {"message: Welcome to the Fitness Tracker"}


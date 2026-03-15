from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import json
import os

app = FastAPI()

DATA_FILE = "modules/logistikk-og-ordre/intern-lassplan/data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"orders": []}, f)

app.mount("/static", StaticFiles(directory="modules/logistikk-og-ordre/intern-lassplan/static"), name="static")


@app.get("/")
def root():
    return FileResponse("modules/logistikk-og-ordre/intern-lassplan/static/index.html")


@app.get("/api/orders")
def get_orders():
    with open(DATA_FILE) as f:
        return json.load(f)


@app.post("/api/orders")
def save_orders(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)
    return {"status": "ok"}

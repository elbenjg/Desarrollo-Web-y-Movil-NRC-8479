from fastapi import FastAPI

app = FastAPI(
    title = "Backend API en",
    description = "API ubicada y enrutada por API gateway"
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Backend API"
    }

@app.get("/productos")
def products():
    return {
        "productos": [
            {"id": 1, "nombre": "Notebook", "precio": 900000},
            {"id": 2, "nombre": "Monitor", "precio": 250000},
        ]
    }

@app.get("/ordenes")
def orders():
    return {
        "ordenes": [
            {"id": 1001, "status": "paid"},
            {"id": 1002, "status": "pending"},
        ]
    }
from fastapi import FastAPI

from .routes import router

app = FastAPI(title="claims-api")
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}

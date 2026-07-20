"""Minimal FastAPI skeleton — routes land in later phases."""

from fastapi import FastAPI

app = FastAPI(title="arcnet-server", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

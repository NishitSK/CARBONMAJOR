"""
Single-process entry point for a short-lived deploy (e.g. a one-week EC2
demo): mounts the existing FastAPI app under /api and serves the built
React frontend (carbon_scheduler_ui/dist) as static files on everything
else - one process, one port, no nginx/reverse proxy needed.

Build the frontend first:
    cd carbon_scheduler_ui && npm run build

Then run from carbon_scheduler/:
    python server.py
    # or in production: gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8001 server:server
"""
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api import app as api_app

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "carbon_scheduler_ui", "dist")

server = FastAPI(title="Carbon-Aware Scheduler")
server.mount("/api", api_app)

if os.path.isdir(FRONTEND_DIST):
    server.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @server.get("/")
    async def missing_build():
        return {"error": f"Frontend not built. Run `npm run build` in carbon_scheduler_ui/ first. Looked in {FRONTEND_DIST}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:server", host="0.0.0.0", port=8001, reload=False)

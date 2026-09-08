from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, clients, sales, dashboard, queue, reports

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(sales.router)
app.include_router(dashboard.router)
app.include_router(queue.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {"status": "ok", "app": settings.app_name}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
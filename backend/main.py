from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, clients, sales, dashboard, queue, reports
from scheduler import scheduler as reminder_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicia o APScheduler de lembretes ao subir e encerra ao desligar (doc 2.4)."""
    reminder_scheduler.start()
    yield
    reminder_scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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
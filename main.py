import time
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import dispose_engine, wait_for_db
from app.core.redis_config import close_redis, init_redis
from app.modules.auth.auth_router import router as auth_router
from app.modules.employees.employees_router import router as employees_router
from app.modules.organization.organization_router import router as organization_router
from app.modules.party.party_router import parties, party_types
from app.modules.transaction.transaction_router import router as transaction_router
from app.modules.attendance.attendance_router import router as attendance_router
from app.modules.customer.customer_router import router as customer_router
from app.modules.order.order_router import router as order_router

from app.utils.exceptions import register_exception_handlers
from app.utils.logger import get_logger
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await wait_for_db()
    await init_redis()

    yield
    # Shutdown
    await dispose_engine()
    await close_redis()


app = FastAPI(title="My API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    sec = time.perf_counter() - start
    # ms = (time.perf_counter() - start) * 1000

    logger.info(
        # f"{request.method} {request.url.path} -> {response.status_code} ({ms:.1f}ms)"
        f"{request.method} {request.url.path} -> {response.status_code} ({sec:.3f} seconds)"
    )
    return response


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(organization_router)
api_router.include_router(employees_router)
api_router.include_router(party_types)
api_router.include_router(parties)
api_router.include_router(transaction_router)
api_router.include_router(attendance_router)
api_router.include_router(customer_router)
api_router.include_router(order_router)

app.include_router(api_router)


@app.get("/")
def root():
    return {"success": True, "message": "Welcome to the Furniture Management System"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

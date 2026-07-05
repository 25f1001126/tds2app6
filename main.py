from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid
from collections import defaultdict, deque

app = FastAPI()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- CONFIG ----------------
TOTAL_ORDERS = 59
RATE_LIMIT = 16
WINDOW = 10  # seconds

# ---------------- STORAGE ----------------
idempotency_store = {}
rate_store = defaultdict(deque)

# ---------------- RATE LIMIT MIDDLEWARE ----------------
from fastapi.responses import JSONResponse

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client_id = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()
    q = rate_store[client_id]

    while q and now - q[0] > WINDOW:
        q.popleft()

    if len(q) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "10"}
        )

    q.append(now)
    return await call_next(request)


# ---------------- 1. IDEMPOTENT ORDERS ----------------
@app.post("/orders")
async def create_order(request: Request, idempotency_key: str = Header(None)):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key")

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created",
        "ts": time.time()
    }

    idempotency_store[idempotency_key] = order
    return order


# ---------------- 2. CURSOR PAGINATION ----------------
@app.get("/orders")
def get_orders(limit: int = 10, cursor: str = None):
    start = int(cursor) if cursor else 1

    if start < 1:
        start = 1

    end = min(start + limit, TOTAL_ORDERS + 1)

    items = [{"id": i} for i in range(start, end)]

    next_cursor = str(end) if end <= TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }

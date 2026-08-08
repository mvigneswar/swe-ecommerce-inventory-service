# 🛍️ SWE Project 2 — E-Commerce RESTful API & Inventory Management Service

> Build plan + prerequisites. Derived from `02_Software_Engineering_Projects_Blueprint.md` (Project 2)
> and `01_IDE_and_GitHub_Integration_Guide.md`.

---

## 0. Project Identity

| Field | Value |
| :--- | :--- |
| Repo name | `swe-ecommerce-inventory-service` |
| Local path | `c:\Users\Vigneswar\Documents\projects\swe-ecommerce-inventory-service` |
| GitHub | `https://github.com/mvigneswar/swe-ecommerce-inventory-service` |
| Target role | Backend Engineer / SDE-1 (Python + SQL) |
| Core stack | Python 3.12, Flask, SQLAlchemy, PyMySQL, MySQL 8, Redis 7, Docker Compose, pytest |
| Headline claims | Redis caching (sub-10ms catalog reads), ACID stock decrement with `SELECT ... FOR UPDATE` row locks, layered architecture, containerized |

---

## 1. Prerequisites Checklist

### 1.1 Already satisfied ✅
- Git 2.55.0 + global identity configured (`mvigneswar` / `vigneswarmadhala@gmail.com`)
- GitHub CLI 2.97
- Docker CLI 29.6.2 + Docker Compose v5.3.1
- WSL2 enabled

### 1.2 Must install / start ❌

| # | Item | Why | How |
| :-- | :--- | :--- | :--- |
| P1 | **Python 3.12** | Runtime for Flask app, venv, pytest | `winget install --id Python.Python.3.12 -e --source winget` then **restart terminal** |
| P2 | **Start Docker Desktop** | Engine is not running; needed for MySQL + Redis | Launch Docker Desktop, wait for "Engine running" |
| P3 | **GitHub CLI login** | Push repo without PAT juggling | `gh auth login` → GitHub.com → HTTPS → login via browser |
| P4 | MySQL 8 | Primary datastore | **Docker container** (no native install) |
| P5 | Redis 7 | Cache layer | **Docker container** (no native install) |

### 1.3 Recommended VS Code extensions
- `ms-python.python` + `ms-python.vscode-pylance`
- `ms-python.debugpy`
- `charliermarsh.ruff` (lint/format)
- `humao.rest-client` (test APIs from `.http` files — lighter than Postman)
- `cweijan.vscode-mysql-client2` (browse MySQL/Redis in the sidebar)
- `ms-azuretools.vscode-docker`

### 1.4 Ports we will occupy
| Port | Service |
| :--- | :--- |
| 5000 | Flask API |
| 3307 | MySQL (host side — mapped to container 3306 to avoid clashes) |
| 6379 | Redis |

---

## 2. Target Architecture

```
Client (REST Client / Postman)
        │
        ▼
┌────────────────────────────┐
│  Flask App (app factory)   │
│  ├─ routes/  (blueprints)  │  ← HTTP layer, validation, status codes
│  ├─ controllers/ (logic)   │  ← business rules, transactions
│  ├─ services/ (redis)      │  ← cross-cutting cache
│  └─ models/  (SQLAlchemy)  │  ← ORM entities
└──────┬──────────────┬──────┘
       │              │
   ┌───▼───┐      ┌───▼────┐
   │ MySQL │      │ Redis  │
   │  :3307│      │  :6379 │
   └───────┘      └────────┘
```

**Layering rule:** routes never touch the DB directly; controllers never build HTTP responses beyond `(dict, status_code)`.

---

## 3. Directory Structure (final target)

```text
swe-ecommerce-inventory-service/
├── app/
│   ├── __init__.py            # create_app() factory, blueprint + ext registration
│   ├── config.py              # Dev/Test/Prod config classes from env
│   ├── extensions.py          # db = SQLAlchemy(), shared singletons
│   ├── controllers/
│   │   ├── product_controller.py
│   │   └── order_controller.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── product.py
│   │   └── order.py           # Order + OrderItem
│   ├── routes/
│   │   ├── product_routes.py
│   │   ├── order_routes.py
│   │   └── health_routes.py
│   ├── schemas/
│   │   └── validators.py      # request payload validation
│   ├── services/
│   │   └── redis_service.py   # get/set/invalidate + graceful degradation
│   └── utils/
│       ├── errors.py          # AppError, global error handler
│       └── responses.py       # ok() / fail() helpers
├── db/
│   └── init.sql               # schema DDL, auto-run by MySQL container
├── scripts/
│   └── seed_data.py           # bulk-insert demo products
├── tests/
│   ├── conftest.py
│   ├── test_products.py
│   ├── test_orders.py
│   └── test_cache.py
├── requests/
│   └── api.http               # REST Client collection
├── .env.example
├── .env                       # gitignored
├── .gitignore
├── .dockerignore
├── app.py                     # entrypoint
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
└── README.md
```

---

## 4. Database Schema

`products` · `orders` · `order_items` — exactly per blueprint, plus these hardening additions:

- `products`: index on `category`, `CHECK (stock_quantity >= 0)`, `updated_at`
- `orders`: index on `customer_email`
- `order_items`: composite index `(order_id, product_id)`
- Engine `InnoDB` (required for row-level locking + FK), charset `utf8mb4`

---

## 5. API Surface

| Method | Endpoint | Description | Cache behaviour |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Liveness + MySQL/Redis connectivity | — |
| `GET` | `/api/products` | List products; `?category=` `?page=` `?limit=` | Redis, TTL 60s |
| `GET` | `/api/products/<id>` | Single product | Redis, TTL 60s |
| `POST` | `/api/products` | Create product | Invalidates `products:*` |
| `PUT` | `/api/products/<id>` | Update product | Invalidates `products:*` |
| `DELETE` | `/api/products/<id>` | Delete product | Invalidates `products:*` |
| `POST` | `/api/orders` | Place order, atomically decrement stock | DB transaction + invalidate |
| `GET` | `/api/orders/<id>` | Order detail with line items | Direct DB |

**Uniform response envelope**
```json
{ "success": true,  "data": { }, "meta": { "cached": true, "response_time_ms": 4 } }
{ "success": false, "error": { "code": "INSUFFICIENT_STOCK", "message": "..." } }
```

---

## 6. Build Phases

### Phase 0 — Environment (blocking)
- [ ] Install Python 3.12 (`winget`), restart terminal, verify `python --version`
- [ ] Start Docker Desktop, verify `docker info`
- [ ] `gh auth login`

### Phase 1 — Repo bootstrap
- [ ] `git init -b main`
- [ ] `.gitignore` **first** (venv, `__pycache__`, `.env`, `.pytest_cache`, `*.db`)
- [ ] `.env.example` + `.env`
- [ ] Create venv, install deps, freeze `requirements.txt`
- [ ] Create GitHub repo + first push (`chore: initial project scaffold`)

### Phase 2 — Infrastructure
- [ ] `docker-compose.yml` → `mysql:8.0` + `redis:7-alpine` with named volumes + healthchecks
- [ ] `db/init.sql` auto-mounted to `/docker-entrypoint-initdb.d`
- [ ] `docker compose up -d mysql redis`; verify both healthy

### Phase 3 — App skeleton
- [ ] `app/config.py`, `app/extensions.py`, `app/__init__.py` (factory), `app.py`
- [ ] `/api/health` returning DB + Redis ping status
- [ ] Commit: `feat: flask app factory with health endpoint`

### Phase 4 — Models
- [ ] `Product`, `Order`, `OrderItem` with `to_dict()` serializers and relationships
- [ ] Commit: `feat: sqlalchemy models for product, order, order_item`

### Phase 5 — Redis service
- [ ] Connection pool, `get/set/invalidate`, **fail-open** if Redis is down
- [ ] Deterministic cache-key builder (`products:list:<category>:<page>:<limit>`)
- [ ] Commit: `feat: redis caching service with graceful degradation`

### Phase 6 — Product API
- [ ] Controller + routes for full CRUD, filtering, pagination
- [ ] Cache-aside read path; invalidate on every write
- [ ] Commit: `feat: product catalog api with redis cache-aside`

### Phase 7 — Order API (the money feature)
- [ ] `create_order_transaction` with `with_for_update()` row locks
- [ ] Rollback on insufficient stock, deterministic lock ordering (sort by product id) to avoid deadlocks
- [ ] Commit: `feat: atomic order placement with row-level stock locking`

### Phase 8 — Cross-cutting
- [ ] Payload validation, global error handler, structured JSON logging, request-timing middleware
- [ ] Commit: `feat: validation, error handling and request logging`

### Phase 9 — Tests
- [ ] pytest + fixtures; unit tests for cache, integration tests for products/orders
- [ ] Concurrency test: two simultaneous orders on last stock unit → exactly one wins
- [ ] Commit: `test: api and concurrency test suite`

### Phase 10 — Containerize the app
- [ ] `Dockerfile` (slim base, non-root user, gunicorn)
- [ ] Add `api` service to compose; whole stack up with one command
- [ ] Commit: `chore: dockerize flask service`

### Phase 11 — Polish & showcase
- [ ] `scripts/seed_data.py` (~100 demo products)
- [ ] `requests/api.http` collection
- [ ] Benchmark cached vs uncached latency → put real numbers in README
- [ ] Production README with badges, architecture diagram, benchmark table
- [ ] GitHub topics: `python`, `flask`, `mysql`, `redis`, `rest-api`, `docker`, `backend`, `iit-madras`
- [ ] Commit: `docs: production readme with benchmarks`

---

## 7. Commit Convention
Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
One commit per phase minimum — keeps the contribution graph and history recruiter-friendly.

---

## 8. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| Docker Desktop won't start (WSL) | `wsl --update`, enable Virtualization in BIOS |
| Port 3306 already used | Host port mapped to **3307** by default |
| MySQL container slow first boot | Healthcheck + app retry loop on startup |
| Redis down in prod | Cache service fails open → API still serves from MySQL |
| Deadlocks on concurrent orders | Lock rows in ascending product-id order |
| `.env` accidentally committed | `.gitignore` created before any `git add` |

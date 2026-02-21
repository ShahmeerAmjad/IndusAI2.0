# MRO Platform

Agentic back-office / middle-office operating system for industrial MRO (Maintenance, Repair & Operations) distributors.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, asyncpg, Redis |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts |
| **Database** | PostgreSQL 16, Redis 7 |
| **AI** | Anthropic Claude (circuit-breaker protected) |
| **Infra** | Docker Compose, GitHub Actions CI |

## Features

- **Product Catalog** — SKU management, specs, cross-references, categories, hazmat tracking
- **Inventory Management** — Multi-warehouse stock levels, reorder alerts, bin locations, transaction history
- **Order-to-Cash (O2C)** — Full order lifecycle: draft, submit, confirm, ship, deliver, cancel
- **Quoting** — Create, send, accept, and convert quotes to orders
- **Dynamic Pricing** — Price lists, quantity tiers, customer contracts
- **Procurement (P2P)** — Supplier management, purchase orders, goods receipt, auto-generation from reorder alerts
- **Invoicing & Payments** — Invoice lifecycle, payment recording, AR aging analysis
- **RMA / Returns** — Return authorization, approval workflow, goods receipt, refund processing
- **Workflow Engine** — Configurable state machines for orders, POs, RMAs, credit and price approvals
- **Analytics Dashboard** — KPIs, revenue trends, top products/customers, real-time operational overview
- **AI Chat Assistant** — Natural language queries for orders, products, and pricing
- **Omnichannel Messaging** — WhatsApp Business API integration with webhook verification
- **Monitoring** — Prometheus metrics, health checks, structured logging

## Architecture

```
┌──────────────────────────────────────────────────┐
│                   React Frontend                  │
│  (Vite + TypeScript + Tailwind + React Query)     │
└────────────────────┬─────────────────────────────┘
                     │  /api/v1/*
┌────────────────────▼─────────────────────────────┐
│                FastAPI Backend                     │
│  ┌─────────┐ ┌──────────┐ ┌────────────────────┐ │
│  │  Auth   │ │  Rate    │ │  Security Headers  │ │
│  │  (JWT)  │ │  Limiter │ │  Middleware         │ │
│  └─────────┘ └──────────┘ └────────────────────┘ │
│                                                   │
│  ┌─ Platform Services (15 modules) ─────────────┐ │
│  │ Product · Inventory · Customer · Pricing     │ │
│  │ Order · Quote · Procurement · Invoice        │ │
│  │ RMA · Workflow · Analytics · ERP Connector   │ │
│  └──────────────────────────────────────────────┘ │
│                                                   │
│  ┌─ Core Services ──────────────────────────────┐ │
│  │ AI (Claude) · Chatbot · Intent Classifier    │ │
│  │ Business Logic · Spam Detector · Escalation  │ │
│  └──────────────────────────────────────────────┘ │
└───────┬──────────────────────────┬───────────────┘
        │                          │
   ┌────▼────┐               ┌────▼────┐
   │PostgreSQL│               │  Redis  │
   │  (data)  │               │ (cache) │
   └─────────┘               └─────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ and npm (for frontend development)
- Python 3.12+ (for backend development without Docker)

### 1. Clone and configure

```sh
git clone <repo-url> && cd IndusAI2.0
cp .env.example .env
```

Edit `.env` and set at minimum:

```
SECRET_KEY=your-secret-key-at-least-32-characters-long
DATABASE_URL=postgresql://chatbot:password@localhost:5432/chatbot
REDIS_URL=redis://localhost:6379/0
```

### 2. Run with Docker Compose (recommended)

```sh
docker compose up -d
```

This starts PostgreSQL, Redis, and the backend API on port **8000**.

### 3. Run the frontend

```sh
npm install
npm run dev
```

Frontend starts on port **8080** and proxies `/api` requests to the backend.

### 4. Open the app

Navigate to `http://localhost:8080`.

## Development

### Backend

```sh
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```sh
npm run dev       # Development server with HMR
npm run build     # Production build (output: dist/)
npm run lint      # ESLint
npm test          # Vitest (28 tests)
npm run test:watch # Vitest watch mode
```

### Type checking

```sh
npx tsc --noEmit -p tsconfig.app.json
```

## API Overview

52 REST endpoints under `/api/v1`:

| Module | Endpoints | Methods |
|--------|-----------|---------|
| Products | `/products`, `/products/{id}`, `/products/sku/{sku}`, `/products/categories` | GET, POST, PATCH |
| Inventory | `/inventory`, `/inventory/reorder-alerts`, `/inventory/adjust` | GET, POST |
| Customers | `/customers`, `/customers/{id}`, `/customers/{id}/credit` | GET, POST |
| Pricing | `/pricing/{id}`, `/pricing/{id}/tiers`, `/price-lists`, `/contracts` | GET, POST |
| Orders | `/orders`, `/orders/{id}`, `/orders/{id}/submit\|confirm\|ship\|deliver\|cancel` | GET, POST, PATCH |
| Quotes | `/quotes`, `/quotes/{id}`, `/quotes/{id}/send\|accept\|convert` | GET, POST |
| Suppliers | `/suppliers`, `/suppliers/{id}` | GET, POST |
| Purchase Orders | `/purchase-orders`, `/purchase-orders/auto-generate` | GET, POST |
| Invoices | `/invoices`, `/invoices/aging`, `/invoices/overdue` | GET, POST |
| Payments | `/payments` | POST |
| RMA | `/rma`, `/rma/{id}`, `/rma/{id}/approve\|receive\|refund` | GET, POST |
| Workflows | `/workflows`, `/workflows/{id}/transition` | GET, POST |
| Analytics | `/analytics/dashboard`, `/analytics/sales` | GET |
| Chat | `/message` | POST |

Health and monitoring: `GET /health`, `GET /health/detailed`, `GET /metrics`

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | JWT signing key (32+ characters) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `ANTHROPIC_API_KEY` | No | Enables AI chat assistant |
| `ADMIN_API_KEY` | Prod | Admin API access token |
| `WHATSAPP_ACCESS_TOKEN` | No | WhatsApp Business API |
| `RATE_LIMIT_PER_MINUTE` | No | API rate limit (default: 60) |

## CI/CD

GitHub Actions runs on push/PR to `main` and `develop`:

**Frontend job:** lint, type-check, test (28 tests), build
**Backend job:** ruff lint, mypy type-check

## Project Structure

```
├── main.py                    # FastAPI app, routes, middleware
├── services/
│   ├── ai_service.py          # Claude AI with circuit breaker
│   ├── business_logic.py      # Core business logic
│   ├── chatbot_engine.py      # Message processing
│   ├── database_manager.py    # PostgreSQL + Redis connections
│   ├── intent_classifier.py   # NLP intent detection
│   └── platform/
│       ├── schema.py          # Database schema (25+ tables)
│       ├── seed.py            # Demo seed data
│       ├── product_service.py
│       ├── inventory_service.py
│       ├── order_service.py
│       ├── quote_service.py
│       ├── pricing_service.py
│       ├── procurement_service.py
│       ├── invoice_service.py
│       ├── rma_service.py
│       ├── customer_service.py
│       ├── analytics_service.py
│       └── workflow_engine.py
├── src/
│   ├── App.tsx                # Route config (lazy-loaded)
│   ├── components/
│   │   ├── ErrorBoundary.tsx
│   │   └── layout/           # AppLayout, Sidebar, Header
│   ├── lib/
│   │   ├── api.ts            # Typed API client (27 methods)
│   │   └── utils.ts          # formatCurrency, statusColor, cn
│   ├── pages/                # 11 page components
│   └── __tests__/            # 3 test suites, 28 tests
├── docker-compose.yml         # PostgreSQL + Redis + Backend
├── Dockerfile                 # Multi-stage Python 3.12
├── .github/workflows/ci.yml  # GitHub Actions pipeline
├── package.json
├── requirements.txt
├── vite.config.ts
└── tailwind.config.ts
```

## License

Proprietary. All rights reserved.

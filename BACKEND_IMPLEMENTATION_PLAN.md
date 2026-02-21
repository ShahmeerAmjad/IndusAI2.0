# Backend Implementation Plan - IndustrialIQ

## Overview
This document outlines the backend implementation required to meet the CRITICAL requirements identified in the gap analysis.

---

## Technology Stack

### Core Backend
- **Runtime**: Node.js 20 LTS
- **Framework**: Express.js with TypeScript
- **API Style**: REST + WebSocket for real-time chat

### Database Layer
- **Primary DB**: PostgreSQL 15 (structured data)
- **Vector DB**: pgvector extension (similarity search)
- **Cache/Sessions**: Redis (conversation state, 24-hour sessions)
- **Search**: PostgreSQL full-text search (can upgrade to Elasticsearch later)

### AI/NLP Layer
- **Orchestration**: LangChain.js
- **LLM**: OpenAI GPT-4 / Claude API
- **Entity Extraction**: Custom NER with LangChain
- **Intent Classification**: Fine-tuned classifier

### Integrations
- **ERP**: SAP Business One API / Oracle REST APIs
- **Messaging**: Twilio (SMS), WhatsApp Business API
- **Email**: SendGrid

---

## Directory Structure

```
/server
├── /src
│   ├── /config          # Configuration files
│   ├── /controllers     # Route controllers
│   ├── /services        # Business logic
│   │   ├── /ai          # AI/NLP services
│   │   ├── /inventory   # Inventory management
│   │   ├── /orders      # Order processing
│   │   └── /messaging   # Communication channels
│   ├── /models          # Database models (Prisma)
│   ├── /routes          # API routes
│   ├── /middleware      # Auth, validation, etc.
│   ├── /utils           # Helper functions
│   └── /types           # TypeScript types
├── /prisma              # Database schema
├── package.json
├── tsconfig.json
└── .env.example
```

---

## CRITICAL Features Implementation

### 1. AI Engine (Priority: CRITICAL)

#### 1.1 NLP-Based Recognition
```typescript
// Using LangChain for conversation handling
import { ChatOpenAI } from "@langchain/openai";
import { ConversationChain } from "langchain/chains";

const llm = new ChatOpenAI({ modelName: "gpt-4" });
const chain = new ConversationChain({ llm });
```

#### 1.2 Entity Extraction
- Part numbers: Regex + LLM validation
- Quantities: Number extraction with context
- Dates: chrono-node library

#### 1.3 Intent Classification
Categories:
- PRODUCT_INQUIRY
- PRICE_REQUEST
- ORDER_PLACEMENT
- ORDER_STATUS
- TECHNICAL_SUPPORT
- RETURNS
- GENERAL_QUESTION

#### 1.4 Conversation State Tracking
- Redis-based session management
- 24-hour TTL for conversations
- State machine for conversation flow

### 2. Data Layer (Priority: CRITICAL)

#### 2.1 PostgreSQL Schema
```prisma
model Product {
  id          String   @id
  name        String
  description String?
  specs       Json
  price       Decimal
  stock       Int
  embedding   Float[]  @db.Vector(1536)
}

model Conversation {
  id        String    @id @default(uuid())
  channel   String
  customerId String?
  state     Json
  messages  Message[]
  createdAt DateTime  @default(now())
  updatedAt DateTime  @updatedAt
}

model Message {
  id             String       @id @default(uuid())
  conversationId String
  conversation   Conversation @relation(fields: [conversationId], references: [id])
  role           String       // user, assistant, system
  content        String
  metadata       Json?
  createdAt      DateTime     @default(now())
}

model Order {
  id         String   @id @default(uuid())
  customerId String
  items      Json
  status     String
  total      Decimal
  createdAt  DateTime @default(now())
}
```

#### 2.2 Vector Search (pgvector)
```sql
CREATE EXTENSION vector;
-- Enables similarity search on product embeddings
```

### 3. Integration Layer (Priority: CRITICAL)

#### 3.1 ERP Integration
```typescript
interface ERPConnector {
  getInventory(productId: string): Promise<InventoryData>;
  createOrder(order: OrderData): Promise<OrderResult>;
  getOrderStatus(orderId: string): Promise<OrderStatus>;
}
```

#### 3.2 Messaging Integration
```typescript
interface MessagingService {
  sendSMS(to: string, message: string): Promise<void>;
  sendWhatsApp(to: string, message: string): Promise<void>;
  sendEmail(to: string, subject: string, body: string): Promise<void>;
}
```

---

## API Endpoints

### Conversations
- `POST /api/conversations` - Create new conversation
- `GET /api/conversations/:id` - Get conversation with messages
- `POST /api/conversations/:id/messages` - Send message (triggers AI response)
- `GET /api/conversations/:id/history` - Get conversation history

### Products/Inventory
- `GET /api/products` - List products
- `GET /api/products/:id` - Get product details
- `GET /api/products/search` - Search with filters
- `POST /api/products/semantic-search` - Vector similarity search

### Orders
- `POST /api/orders` - Create order
- `GET /api/orders/:id` - Get order status
- `PUT /api/orders/:id` - Update order
- `GET /api/orders/customer/:customerId` - Customer orders

### Quotes
- `POST /api/quotes` - Generate quote
- `GET /api/quotes/:id` - Get quote details

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/industrialiq
REDIS_URL=redis://localhost:6379

# AI/LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Messaging
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...
SENDGRID_API_KEY=...

# ERP
SAP_API_URL=...
SAP_API_KEY=...
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [x] Backend project setup
- [x] Database schema (Prisma)
- [x] Basic API routes
- [x] Authentication middleware

### Phase 2: AI/NLP (Week 2)
- [ ] LangChain integration
- [ ] Intent classification
- [ ] Entity extraction
- [ ] Conversation flow management

### Phase 3: Integrations (Week 3)
- [ ] ERP connector (mock first, then real)
- [ ] Inventory sync
- [ ] Order processing

### Phase 4: Messaging (Week 4)
- [ ] Twilio SMS integration
- [ ] WhatsApp Business API
- [ ] Email notifications

---

## Testing Strategy

- Unit tests: Jest
- Integration tests: Supertest
- E2E tests: Playwright (frontend + backend)

---

## Deployment

- Docker containerization
- Docker Compose for local dev
- Production: AWS ECS / Google Cloud Run

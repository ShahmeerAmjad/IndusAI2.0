# Demo Landing Page & UI Enhancement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a public landing page showcasing what's built, upgrade the dashboard and AI chat to premium quality, and polish all pages for a co-founder demo.

**Architecture:** New public `Landing.tsx` page at `/`, Dashboard moves to `/dashboard`. Chat gets streaming text, dark mode, side panel, and AI thinking stages. All pages unified to `industrial-*`/`tech-*`/`neutral-*` palette. Responsive sidebar with collapse behavior.

**Tech Stack:** React 18, react-router-dom v6, Tailwind CSS, Recharts, Lucide icons, Framer Motion (new — for animations), Radix UI primitives (already installed).

**Design doc:** `docs/plans/2026-03-02-demo-landing-ui-design.md`

---

## Batch 1: Foundation & Landing Page (Tasks 1-3)

### Task 1: Install Framer Motion & Route Restructuring

**Files:**
- Modify: `package.json` (add framer-motion)
- Modify: `src/App.tsx:1-98` (add Landing route, move Dashboard)

**Step 1: Install framer-motion**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm install framer-motion`
Expected: Package added to dependencies

**Step 2: Update App.tsx routes**

Add Landing lazy import and restructure routes so `/` → Landing (public), `/dashboard` → Dashboard (protected):

```tsx
// Add at top with other lazy imports
const Landing = lazy(() => import("@/pages/Landing"));

// In the Routes:
// 1. Add Landing as a PUBLIC route (outside RequireAuth, outside PublicOnly)
<Route path="/landing" element={<Suspense fallback={<FullPageLoader />}><Landing /></Suspense>} />

// 2. Change Dashboard route from "/" to "/dashboard"
<Route path="/dashboard" element={<Suspense fallback={<PageLoader />}><Dashboard /></Suspense>} />

// 3. Remove the Sourcing route entirely
// DELETE: <Route path="/sourcing" ...

// 4. Update catch-all to redirect to /landing instead of /
<Route path="*" element={<Navigate to="/landing" replace />} />

// 5. Update PublicOnly redirect: if user is logged in, redirect to /dashboard not /
if (user) return <Navigate to="/dashboard" replace />;
```

**Step 3: Update Sidebar dashboard link**

In `src/components/layout/Sidebar.tsx:29`, change Dashboard `to` from `"/"` to `"/dashboard"`:
```tsx
{ to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
```

Also remove the Intelligence section with Sourcing link (lines 46-51).

**Step 4: Update NavLink `end` prop**

In `src/components/layout/Sidebar.tsx:88`, change `end={item.to === "/"}` to `end={item.to === "/dashboard"}`.

**Step 5: Update Header PAGE_TITLES**

In `src/components/layout/Header.tsx:5-17`, change `"/"` key to `"/dashboard"` and add missing entries:
```tsx
const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/products": "Product Catalog",
  "/inventory": "Inventory Management",
  "/orders": "Order Management",
  "/quotes": "Quotes",
  "/procurement": "Procurement",
  "/invoices": "Invoicing & Payments",
  "/rma": "Returns & RMA",
  "/channels": "Omnichannel Hub",
  "/chat": "AI Sourcing Assistant",
  "/bulk-import": "Bulk Import",
  "/admin": "Admin Debug View",
};
```

**Step 6: Verify dev server starts**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds (Landing.tsx doesn't exist yet — that's fine, it's lazy-loaded)

**Step 7: Commit**

```bash
git add package.json package-lock.json src/App.tsx src/components/layout/Sidebar.tsx src/components/layout/Header.tsx
git commit -m "refactor: restructure routes for landing page, remove Sourcing page"
```

---

### Task 2: Landing Page — Hero & Navigation

**Files:**
- Create: `src/pages/Landing.tsx`

**Step 1: Create the Landing page with hero and nav**

Create `src/pages/Landing.tsx` with:
- Top nav bar: Logo + "IndusAI" text (left), anchor links Features / Tech / Stats (center), Login + Sign Up buttons (right, linking to /login and /signup)
- Hero section: full-width dark gradient (`bg-gradient-to-br from-slate-900 via-slate-800 to-industrial-900`), white heading "The Operating System for MRO Distribution", subheading, two CTA buttons ("Get Started" → /signup, "Explore Features" → smooth scroll to #features)
- Use `framer-motion` for fade-in animation on hero text

```tsx
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Search, Database, ShoppingCart, Truck, Brain, FileText,
  MessageSquare, Shield, ArrowRight, ChevronDown,
} from "lucide-react";

// Feature card data
const FEATURES = [
  { icon: Search, title: "AI Sourcing Engine", description: "Natural language part search with 5-stage GraphRAG pipeline. Results ranked by price, delivery, and proximity.", color: "from-industrial-600 to-industrial-800" },
  { icon: Database, title: "Knowledge Graph", description: "Neo4j-powered part intelligence with cross-references, specs, and compatibility mapping across suppliers.", color: "from-tech-600 to-tech-800" },
  { icon: ShoppingCart, title: "Order-to-Cash", description: "Complete O2C flow — products, inventory, orders, quotes, invoicing, payments, and returns management.", color: "from-blue-600 to-blue-800" },
  { icon: Truck, title: "Procure-to-Pay", description: "Supplier management, purchase orders, goods receipts, and auto-PO generation from reorder alerts.", color: "from-indigo-600 to-indigo-800" },
  { icon: Brain, title: "Intelligence Layer", description: "Reliability scoring with age decay, composite price comparison, location optimization, and freshness scheduling.", color: "from-purple-600 to-purple-800" },
  { icon: FileText, title: "Reports & Bulk Ops", description: "CSV, Excel, and PDF report generation. Bulk CSV import with dry-run validation and downloadable templates.", color: "from-amber-600 to-amber-800" },
  { icon: MessageSquare, title: "Omnichannel", description: "Web, WhatsApp, email, and SMS messaging with intent classification, escalation management, and routing.", color: "from-emerald-600 to-emerald-800" },
  { icon: Shield, title: "Multi-Tenant Auth", description: "JWT access + refresh token rotation, org-scoped data, bcrypt hashing, and role-based access control.", color: "from-rose-600 to-rose-800" },
];

const STATS = [
  { value: "100+", label: "API Endpoints" },
  { value: "227", label: "Tests Passing" },
  { value: "5-Stage", label: "AI Pipeline" },
  { value: "16", label: "App Pages" },
  { value: "Full", label: "O2C + P2P" },
];

const TECH_STACK = [
  { name: "React", color: "#61DAFB" },
  { name: "FastAPI", color: "#009688" },
  { name: "Neo4j", color: "#008CC1" },
  { name: "PostgreSQL", color: "#336791" },
  { name: "Redis", color: "#DC382D" },
  { name: "Claude AI", color: "#D97706" },
  { name: "Voyage AI", color: "#7C3AED" },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      {/* Hero */}
      {/* Stats bar */}
      {/* Feature cards */}
      {/* Tech stack */}
      {/* Footer */}
    </div>
  );
}
```

Each section should be a self-contained `<section>` with `id` for anchor links. The hero takes full viewport height minus nav. Feature cards are a responsive `grid-cols-1 md:grid-cols-2 lg:grid-cols-4` grid.

**Step 2: Verify it renders**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/pages/Landing.tsx
git commit -m "feat: add landing page with hero, features, stats, and tech stack"
```

---

### Task 3: Delete Sourcing.tsx & Add CSS Animations

**Files:**
- Delete: `src/pages/Sourcing.tsx`
- Modify: `src/index.css` (add keyframes for landing page animations)
- Modify: `tailwind.config.ts` (add new animation utilities)

**Step 1: Delete Sourcing.tsx**

```bash
rm /Users/shahmeer/Documents/IndusAI2/IndusAI2.0/src/pages/Sourcing.tsx
```

**Step 2: Remove Sourcing lazy import from App.tsx**

In `src/App.tsx`, delete line 19: `const Sourcing = lazy(() => import("@/pages/Sourcing"));`

**Step 3: Add new keyframe animations to tailwind.config.ts**

Add these keyframes to `tailwind.config.ts:109` (inside `keyframes`):
```ts
'fade-in-up': {
  '0%': { opacity: '0', transform: 'translateY(20px)' },
  '100%': { opacity: '1', transform: 'translateY(0)' },
},
'fade-in': {
  '0%': { opacity: '0' },
  '100%': { opacity: '1' },
},
'slide-in-right': {
  '0%': { opacity: '0', transform: 'translateX(100%)' },
  '100%': { opacity: '1', transform: 'translateX(0)' },
},
'slide-out-right': {
  '0%': { opacity: '1', transform: 'translateX(0)' },
  '100%': { opacity: '0', transform: 'translateX(100%)' },
},
'typewriter': {
  '0%': { opacity: '0' },
  '100%': { opacity: '1' },
},
'scale-in': {
  '0%': { opacity: '0', transform: 'scale(0.95)' },
  '100%': { opacity: '1', transform: 'scale(1)' },
},
```

Add corresponding animation utilities to `animation` (line 131):
```ts
'fade-in-up': 'fade-in-up 0.5s ease-out',
'fade-in': 'fade-in 0.3s ease-out',
'slide-in-right': 'slide-in-right 0.3s ease-out',
'slide-out-right': 'slide-out-right 0.3s ease-out',
'scale-in': 'scale-in 0.2s ease-out',
```

**Step 4: Add dark mode CSS vars for chat**

In `src/index.css`, add after the `:root` block (inside `@layer base`):
```css
.chat-dark {
  --chat-bg: 222 47% 8%;
  --chat-surface: 222 47% 12%;
  --chat-border: 217 33% 20%;
  --chat-text: 210 40% 92%;
  --chat-text-muted: 215 16% 58%;
  --chat-user-bubble: 217 91% 35%;
  --chat-ai-bubble: 222 47% 15%;
  --chat-ai-glow: 217 91% 50%;
}
```

**Step 5: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add -A
git commit -m "chore: delete Sourcing page, add animations and chat dark mode CSS"
```

---

## Batch 2: Dashboard Upgrade (Tasks 4-6)

### Task 4: Dashboard Welcome Header & Quick Actions

**Files:**
- Modify: `src/pages/Dashboard.tsx:305-316` (add welcome header and quick actions bar)

**Step 1: Add welcome header**

Replace the "Page Header" section (lines 307-315) with a welcome header that uses the auth context:

```tsx
import { useAuth } from "@/lib/auth";
import { Link } from "react-router-dom";
import { Search, Plus, Upload, Download, Activity } from "lucide-react";

// Inside Dashboard component:
const { user } = useAuth();
const hour = new Date().getHours();
const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

// In render, replace Page Header:
<div className="flex items-center justify-between">
  <div>
    <h1 className="font-montserrat text-2xl font-bold text-slate-900">
      {greeting}, {user?.name?.split(" ")[0] || "there"}
    </h1>
    <p className="mt-1 text-sm text-slate-500">
      {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
      {user?.org_name && <span className="ml-2 rounded-full bg-industrial-100 px-2.5 py-0.5 text-xs font-medium text-industrial-700">{user.org_name}</span>}
    </p>
  </div>
  <div className="flex items-center gap-2">
    <Activity className="h-4 w-4 text-green-500" />
    <span className="text-xs font-medium text-green-600">All Systems Operational</span>
  </div>
</div>
```

**Step 2: Add Quick Actions bar**

Insert after the welcome header, before KPI cards:

```tsx
{/* Quick Actions */}
<div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
  <Link to="/chat" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-industrial-300 hover:shadow-md">
    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-industrial-100 text-industrial-600 transition-colors group-hover:bg-industrial-600 group-hover:text-white">
      <Search className="h-5 w-5" />
    </div>
    <div>
      <p className="text-sm font-semibold text-slate-800">Search Parts</p>
      <p className="text-[11px] text-slate-400">AI sourcing</p>
    </div>
  </Link>
  <Link to="/orders" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-tech-300 hover:shadow-md">
    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-tech-100 text-tech-600 transition-colors group-hover:bg-tech-600 group-hover:text-white">
      <Plus className="h-5 w-5" />
    </div>
    <div>
      <p className="text-sm font-semibold text-slate-800">Create Order</p>
      <p className="text-[11px] text-slate-400">New O2C order</p>
    </div>
  </Link>
  <Link to="/bulk-import" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-amber-300 hover:shadow-md">
    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-600 transition-colors group-hover:bg-amber-600 group-hover:text-white">
      <Upload className="h-5 w-5" />
    </div>
    <div>
      <p className="text-sm font-semibold text-slate-800">Import Data</p>
      <p className="text-[11px] text-slate-400">CSV upload</p>
    </div>
  </Link>
  <a href="/api/v1/reports/orders?format=xlsx" className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:border-purple-300 hover:shadow-md">
    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600 transition-colors group-hover:bg-purple-600 group-hover:text-white">
      <Download className="h-5 w-5" />
    </div>
    <div>
      <p className="text-sm font-semibold text-slate-800">Download Report</p>
      <p className="text-[11px] text-slate-400">Orders XLSX</p>
    </div>
  </a>
</div>
```

**Step 3: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add src/pages/Dashboard.tsx
git commit -m "feat: add welcome header and quick actions to dashboard"
```

---

### Task 5: Dashboard KPI Cards Color Unification

**Files:**
- Modify: `src/pages/Dashboard.tsx:217-285` (unify KPI and alert card colors)

**Step 1: Unify KPI card colors to industrial/tech palette**

Replace the `kpiCards` array colors. Change from `emerald-*`, `blue-*`, `indigo-*` to `industrial-*` and `tech-*`:

```tsx
const kpiCards: KpiCard[] = [
  {
    label: "Revenue Today",
    value: formatCurrency(metrics.revenue_today),
    icon: DollarSign,
    border: "border-l-tech-500",
    bg: "bg-tech-50/60",
    iconBg: "bg-tech-100",
    iconColor: "text-tech-600",
  },
  {
    label: "Orders Today",
    value: formatNumber(metrics.orders_today),
    icon: Package,
    border: "border-l-industrial-600",
    bg: "bg-industrial-50/60",
    iconBg: "bg-industrial-100",
    iconColor: "text-industrial-600",
  },
  {
    label: "Open Orders",
    value: formatNumber(metrics.open_orders),
    icon: ClipboardList,
    border: "border-l-industrial-800",
    bg: "bg-industrial-50/40",
    iconBg: "bg-industrial-100",
    iconColor: "text-industrial-800",
  },
  {
    label: "Revenue This Month",
    value: formatCurrency(metrics.revenue_this_month),
    icon: TrendingUp,
    border: "border-l-tech-600",
    bg: "bg-tech-50/40",
    iconBg: "bg-tech-100",
    iconColor: "text-tech-600",
  },
];
```

**Step 2: Unify alert card colors**

Replace alert card colors — keep the semantic meaning but use the design system:

```tsx
const alertCards: AlertCard[] = [
  {
    label: "Low Stock Items",
    value: metrics.low_stock_items,
    icon: AlertTriangle,
    border: "border-l-amber-500",
    textColor: "text-amber-600",
  },
  {
    label: "Pending Invoices",
    value: metrics.pending_invoices,
    icon: FileText,
    border: "border-l-industrial-400",
    textColor: "text-industrial-600",
  },
  {
    label: "Overdue Invoices",
    value: metrics.overdue_invoices,
    icon: CircleAlert,
    border: "border-l-red-500",
    textColor: "text-red-600",
  },
  {
    label: "Open RMAs",
    value: metrics.open_rmas,
    icon: RotateCcw,
    border: "border-l-amber-400",
    textColor: "text-amber-600",
  },
];
```

**Step 3: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add src/pages/Dashboard.tsx
git commit -m "style: unify dashboard card colors to industrial/tech palette"
```

---

### Task 6: Dashboard Chart Improvements

**Files:**
- Modify: `src/pages/Dashboard.tsx` (chart section — add area fill, improve colors)

**Step 1: Add area fill to revenue trend line chart**

In `SalesTrendChart` component (around line 146), add an `Area` component from recharts and update the import:

```tsx
import { Area } from "recharts"; // add to recharts import

// In the LineChart, add before the Line component:
<defs>
  <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stopColor="#1e3a8a" stopOpacity={0.15} />
    <stop offset="100%" stopColor="#1e3a8a" stopOpacity={0} />
  </linearGradient>
</defs>
<Area
  type="monotone"
  dataKey="revenue"
  stroke="none"
  fill="url(#revenueGradient)"
/>
```

**Step 2: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/pages/Dashboard.tsx
git commit -m "style: add gradient area fill to revenue trend chart"
```

---

## Batch 3: Chat Premium — Core (Tasks 7-9)

### Task 7: Chat Welcome State & Message Bubble Polish

**Files:**
- Modify: `src/pages/Chat.tsx` (welcome state, bubble styling)

**Step 1: Redesign the welcome state**

Replace the current welcome message + suggested queries (shown when `messages.length === 1`) with a centered welcome UI. When the chat has only the initial welcome message, render a centered hero instead of a regular message bubble:

```tsx
// Replace the welcome message rendering (when messages.length === 1) with:
{messages.length === 1 && !isLoading && (
  <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
    {/* Logo */}
    <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-industrial-600 to-industrial-800 shadow-lg">
      <Search className="h-8 w-8 text-white" />
    </div>
    <h2 className="mt-6 text-xl font-semibold text-slate-800">
      What part are you looking for?
    </h2>
    <p className="mt-2 max-w-md text-center text-sm text-slate-500">
      Describe the MRO part you need. I'll search across suppliers, compare prices, and find the best option.
    </p>
    {/* Suggested queries */}
    <div className="mt-8 flex flex-wrap justify-center gap-2">
      {SUGGESTED_QUERIES.map((q) => (
        <button
          key={q}
          onClick={() => handleSearch(q)}
          disabled={isLoading}
          className="rounded-full border border-industrial-200 bg-industrial-50 px-4 py-2 text-sm font-medium text-industrial-700 transition-all hover:bg-industrial-100 hover:border-industrial-300 hover:shadow-sm disabled:opacity-50"
        >
          {q}
        </button>
      ))}
    </div>
  </div>
)}
```

**Step 2: Polish message bubbles**

Update the message bubble styling — assistant messages switch from flat `bg-gray-100` to white with shadow:

```tsx
// Assistant bubble: change from bg-gray-100 to:
"bg-white border border-slate-200 text-slate-900 rounded-bl-md shadow-sm"

// User bubble: add shadow
"bg-industrial-600 text-white rounded-br-md shadow-md"
```

Add a smooth fade-in using the CSS animation class:
```tsx
<div className={cn("flex animate-fade-in", msg.role === "user" ? "justify-end" : "justify-start")}>
```

**Step 3: Add more suggested queries**

Update `SUGGESTED_QUERIES` to have 6 options:
```tsx
const SUGGESTED_QUERIES = [
  "Find SKF 6205-2RS bearings",
  "Compare hydraulic filters",
  "Need 3M masking tape, 50 rolls",
  "Best price on Fluke 87V multimeter",
  "O-rings for high-temperature use",
  "Parker hydraulic hose 3/8\"",
];
```

**Step 4: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add src/pages/Chat.tsx
git commit -m "feat: redesign chat welcome state and polish message bubbles"
```

---

### Task 8: Chat AI Thinking Stages & Typing Indicator

**Files:**
- Modify: `src/pages/Chat.tsx` (replace loading indicator with thinking stages)

**Step 1: Add thinking stage state and component**

Add state for tracking the current thinking stage:
```tsx
const [thinkingStage, setThinkingStage] = useState(0);

// Add a useEffect to cycle through stages when loading:
useEffect(() => {
  if (!isLoading) {
    setThinkingStage(0);
    return;
  }
  const stages = [0, 1, 2, 3];
  let current = 0;
  const interval = setInterval(() => {
    current = Math.min(current + 1, stages.length - 1);
    setThinkingStage(current);
  }, 800);
  return () => clearInterval(interval);
}, [isLoading]);
```

**Step 2: Replace the bouncing dots with thinking stages**

Replace the loading indicator section (lines 320-342) with:

```tsx
{isLoading && (
  <div className="flex justify-start animate-fade-in">
    <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-white border border-slate-200 px-5 py-4 shadow-sm">
      <div className="space-y-2.5">
        {[
          { icon: Brain, label: "Analyzing your query..." },
          { icon: Database, label: "Searching knowledge graph..." },
          { icon: Building2, label: "Matching sellers..." },
          { icon: BarChart3, label: "Ranking results..." },
        ].map((stage, i) => (
          <div
            key={stage.label}
            className={cn(
              "flex items-center gap-2.5 transition-all duration-300",
              i <= thinkingStage ? "opacity-100" : "opacity-0 h-0 overflow-hidden",
              i === thinkingStage && "text-industrial-600",
              i < thinkingStage && "text-slate-400",
            )}
          >
            <stage.icon className={cn("h-4 w-4 shrink-0", i === thinkingStage && "animate-pulse")} />
            <span className="text-sm">{stage.label}</span>
            {i < thinkingStage && (
              <CheckCircle2 className="h-3.5 w-3.5 text-tech-500 shrink-0" />
            )}
          </div>
        ))}
      </div>
    </div>
  </div>
)}
```

Add `Brain, Database, Building2, CheckCircle2` to the lucide-react imports.

**Step 3: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add src/pages/Chat.tsx
git commit -m "feat: add AI thinking stages indicator to chat"
```

---

### Task 9: Chat Streaming Text Effect

**Files:**
- Modify: `src/pages/Chat.tsx` (add typewriter effect for assistant messages)

**Step 1: Create a useTypewriter hook inline**

Add at the top of `Chat.tsx` (after imports, before the component):

```tsx
function useTypewriter(text: string, speed = 12) {
  const [displayed, setDisplayed] = useState("");
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    if (!text) return;
    setDisplayed("");
    setIsDone(false);
    let i = 0;
    const interval = setInterval(() => {
      // Show words, not characters, for speed
      const words = text.split(" ");
      i = Math.min(i + 1, words.length);
      setDisplayed(words.slice(0, i).join(" "));
      if (i >= words.length) {
        setIsDone(true);
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return { displayed, isDone };
}
```

**Step 2: Track which messages should animate**

Add state to track newly added assistant messages. Only the latest assistant message should animate — older messages render fully:

```tsx
const [animatingIndex, setAnimatingIndex] = useState<number | null>(null);
```

When a new assistant message is added (in `handleSearch`), set `animatingIndex` to the new message index.

**Step 3: Create a TypewriterMessage wrapper component**

```tsx
function TypewriterMessage({ content, onDone }: { content: string; onDone: () => void }) {
  const { displayed, isDone } = useTypewriter(content, 15);

  useEffect(() => {
    if (isDone) onDone();
  }, [isDone, onDone]);

  return (
    <p className="text-sm whitespace-pre-wrap leading-relaxed">
      {displayed}
      {!isDone && <span className="inline-block w-1.5 h-4 bg-industrial-500 ml-0.5 animate-pulse" />}
    </p>
  );
}
```

**Step 4: Use TypewriterMessage for the latest assistant message**

In the message rendering, conditionally use `TypewriterMessage` for the animating message:

```tsx
{msg.role === "assistant" && index === animatingIndex ? (
  <TypewriterMessage content={msg.content} onDone={() => setAnimatingIndex(null)} />
) : (
  <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
)}
```

**Step 5: Add Cmd+Enter keyboard shortcut**

In the `handleKeyDown` function, add:
```tsx
if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
  e.preventDefault();
  handleSearch(input);
}
```

**Step 6: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 7: Commit**

```bash
git add src/pages/Chat.tsx
git commit -m "feat: add streaming typewriter effect and Cmd+Enter shortcut to chat"
```

---

## Batch 4: Chat Premium — Advanced (Tasks 10-12)

### Task 10: Chat Dark Mode Toggle

**Files:**
- Modify: `src/pages/Chat.tsx` (add dark mode toggle and conditional styling)

**Step 1: Add dark mode state**

```tsx
const [darkMode, setDarkMode] = useState(false);
```

**Step 2: Add toggle button in chat header**

In the chat header (between the title and controls), add a Moon/Sun toggle:

```tsx
import { Moon, Sun } from "lucide-react";

// In the header controls area:
<button
  onClick={() => setDarkMode(!darkMode)}
  className={cn(
    "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
    darkMode
      ? "bg-industrial-600 text-white hover:bg-industrial-500"
      : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
  )}
  title={darkMode ? "Light mode" : "Dark mode"}
>
  {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
</button>
```

**Step 3: Apply dark mode classes conditionally**

Wrap the entire chat container with the `chat-dark` class when dark mode is active. Update the key areas:

- Outer container: `bg-white` → `darkMode ? "bg-[hsl(var(--chat-bg))]" : "bg-white"`
- Header: `bg-gray-50` → `darkMode ? "bg-[hsl(var(--chat-surface))] border-[hsl(var(--chat-border))]" : "bg-gray-50 border-gray-200"`
- Messages area: default bg → `darkMode ? "bg-[hsl(var(--chat-bg))]" : ""`
- Assistant bubble: `bg-white border-slate-200` → `darkMode ? "bg-[hsl(var(--chat-ai-bubble))] border-[hsl(var(--chat-border))] text-[hsl(var(--chat-text))]" : "bg-white border-slate-200 text-slate-900"`
- User bubble: keep `bg-industrial-600 text-white` (looks great in both modes)
- Input area: `bg-gray-50` → `darkMode ? "bg-[hsl(var(--chat-surface))]" : "bg-gray-50"`
- Input field: `bg-white` → `darkMode ? "bg-[hsl(var(--chat-bg))] text-white border-[hsl(var(--chat-border))] placeholder-slate-500" : "bg-white text-gray-900 border-gray-300 placeholder-gray-400"`

**Step 4: Add glow effect on assistant bubbles in dark mode**

When dark mode is active, add a subtle glow ring to AI responses:
```tsx
darkMode && "ring-1 ring-[hsl(var(--chat-ai-glow))]/20"
```

**Step 5: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add src/pages/Chat.tsx
git commit -m "feat: add dark mode toggle to chat with glow effects"
```

---

### Task 11: Chat Side Panel — Order & Query History

**Files:**
- Modify: `src/pages/Chat.tsx` (add collapsible side panel)

**Step 1: Add side panel state**

```tsx
const [showPanel, setShowPanel] = useState(false);
```

**Step 2: Add panel toggle button to chat header**

```tsx
import { PanelRightOpen, PanelRightClose, Clock, ShoppingBag } from "lucide-react";

// In header controls:
<button
  onClick={() => setShowPanel(!showPanel)}
  className={cn(
    "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
    showPanel
      ? "bg-industrial-100 text-industrial-600"
      : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
  )}
  title="Toggle history panel"
>
  {showPanel ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
</button>
```

**Step 3: Create the side panel**

Add a right-side panel that slides in. Restructure the chat layout to a flex row — main chat area + optional panel:

```tsx
<div className="flex h-[calc(100vh-10rem)] gap-0">
  {/* Main chat column */}
  <div className={cn("flex flex-1 flex-col rounded-lg border shadow-sm transition-all", /* existing container styles */)}>
    {/* ... existing chat header, messages, input ... */}
  </div>

  {/* Side Panel */}
  {showPanel && (
    <div className="hidden lg:flex w-72 flex-col border rounded-lg shadow-sm ml-4 bg-white animate-slide-in-right overflow-hidden">
      <div className="border-b px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-800">History</h3>
      </div>
      <div className="flex-1 overflow-y-auto">
        {/* Recent Orders */}
        <div className="border-b px-4 py-3">
          <div className="flex items-center gap-2 mb-3">
            <ShoppingBag className="h-4 w-4 text-industrial-500" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Recent Orders</span>
          </div>
          {messages
            .filter(m => m.orderConfirmation)
            .slice(-5)
            .map((m, i) => (
              <div key={i} className="mb-2 rounded-lg bg-slate-50 p-2.5">
                <p className="text-xs font-medium text-slate-700">#{m.orderConfirmation!.order_id}</p>
                <p className="text-[11px] text-slate-400 truncate">{m.content.slice(0, 60)}</p>
              </div>
            ))
          }
          {messages.filter(m => m.orderConfirmation).length === 0 && (
            <p className="text-xs text-slate-400 italic">No orders yet</p>
          )}
        </div>

        {/* Past Queries */}
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="h-4 w-4 text-tech-500" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Past Queries</span>
          </div>
          {messages
            .filter(m => m.role === "user")
            .slice(-10)
            .reverse()
            .map((m, i) => (
              <button
                key={i}
                onClick={() => handleSearch(m.content)}
                disabled={isLoading}
                className="mb-1.5 w-full rounded-lg px-2.5 py-2 text-left text-xs text-slate-600 transition-colors hover:bg-industrial-50 hover:text-industrial-700 disabled:opacity-50"
              >
                <p className="truncate">{m.content}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">{formatTime(m.timestamp)}</p>
              </button>
            ))
          }
        </div>
      </div>
    </div>
  )}
</div>
```

**Step 4: Hide panel on smaller screens**

The panel already uses `hidden lg:flex` so it only appears on large screens.

**Step 5: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add src/pages/Chat.tsx
git commit -m "feat: add collapsible order/query history side panel to chat"
```

---

### Task 12: Rich Result Cards

**Files:**
- Modify: `src/components/sourcing/ResultCard.tsx` (reliability gauge, award badges, expandable)
- Modify: `src/lib/api.ts` (add `reliability` field to SourcingResult if missing)
- Modify: `src/components/sourcing/ComparisonTable.tsx` (auto-expand, sorting)

**Step 1: Add reliability field to SourcingResult type**

In `src/lib/api.ts:258-269`, add `reliability` field:
```tsx
export interface SourcingResult {
  sku: string;
  name: string;
  seller_name: string;
  unit_price: number;
  total_cost: number;
  transit_days: number;
  shipping_cost: number;
  distance_km: number | null;
  qty_available: number;
  manufacturer: string;
  reliability: number;       // 0-10 score
  cross_ref_type?: string;   // if matched via cross-reference
}
```

**Step 2: Create a ReliabilityGauge component**

Add at the top of `ResultCard.tsx`:

```tsx
function ReliabilityGauge({ score }: { score: number }) {
  const normalized = Math.max(0, Math.min(10, score));
  const percentage = (normalized / 10) * 100;
  const color = normalized >= 8 ? "text-tech-500" : normalized >= 6 ? "text-amber-500" : "text-red-500";
  const strokeColor = normalized >= 8 ? "#0d9488" : normalized >= 6 ? "#f59e0b" : "#ef4444";

  return (
    <div className="flex items-center gap-1.5">
      <svg width="24" height="24" viewBox="0 0 24 24" className={color}>
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2" opacity="0.15" />
        <circle
          cx="12" cy="12" r="10" fill="none" stroke={strokeColor} strokeWidth="2.5"
          strokeDasharray={`${percentage * 0.628} 100`}
          strokeLinecap="round"
          transform="rotate(-90 12 12)"
        />
      </svg>
      <span className={cn("text-xs font-semibold", color)}>{normalized.toFixed(1)}</span>
    </div>
  );
}
```

**Step 3: Add award badges**

Determine badges based on result position within the full result set. Pass additional props to ResultCard:

```tsx
interface ResultCardProps {
  result: SourcingResult;
  qty: number;
  rank: number;
  onOrder: (result: SourcingResult) => void;
  onRequestQuote: (result: SourcingResult) => void;
  orderLoading?: boolean;
  isBestPrice?: boolean;
  isFastestDelivery?: boolean;
  isClosest?: boolean;
}
```

Add badges in the header row:
```tsx
<div className="flex flex-wrap gap-1 mt-1">
  {isBestPrice && (
    <span className="rounded-full bg-tech-100 px-2 py-0.5 text-[9px] font-bold text-tech-700 uppercase">Best Price</span>
  )}
  {isFastestDelivery && (
    <span className="rounded-full bg-industrial-100 px-2 py-0.5 text-[9px] font-bold text-industrial-700 uppercase">Fastest</span>
  )}
  {isClosest && (
    <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[9px] font-bold text-purple-700 uppercase">Closest</span>
  )}
</div>
```

**Step 4: Add ReliabilityGauge to the card**

Insert after the meta row:
```tsx
{result.reliability != null && (
  <div className="mt-2 flex items-center gap-2">
    <span className="text-[10px] text-slate-400">Reliability</span>
    <ReliabilityGauge score={result.reliability} />
  </div>
)}
```

**Step 5: Add gradient header to rank 1 card**

For the #1 card, add a gradient top strip:
```tsx
{rank === 1 && (
  <div className="absolute top-0 left-0 right-0 h-1 rounded-t-xl bg-gradient-to-r from-industrial-500 via-tech-500 to-industrial-500" />
)}
// ... wrap the card in `relative overflow-hidden`
```

**Step 6: Compute badges in Chat.tsx**

In `Chat.tsx` where results are rendered, compute which result wins each badge:

```tsx
{msg.sourcing.sourcing_results.map((result, ri) => {
  const results = msg.sourcing!.sourcing_results;
  const isBestPrice = ri === results.reduce((best, r, i) => r.unit_price < results[best].unit_price ? i : best, 0);
  const isFastestDelivery = ri === results.reduce((best, r, i) => r.transit_days < results[best].transit_days ? i : best, 0);
  const isClosest = result.distance_km != null && ri === results.filter(r => r.distance_km != null).reduce((best, r, i) => (r.distance_km! < results.filter(rr => rr.distance_km != null)[best]?.distance_km! ? i : best), 0);

  return (
    <ResultCard
      key={`${result.sku}-${result.seller_name}`}
      result={result}
      qty={qty}
      rank={ri + 1}
      onOrder={handleOrder}
      onRequestQuote={handleRequestQuote}
      orderLoading={orderLoadingFor === `${result.sku}-${result.seller_name}`}
      isBestPrice={isBestPrice}
      isFastestDelivery={isFastestDelivery}
      isClosest={!!isClosest}
    />
  );
})}
```

**Step 7: Update ComparisonTable to auto-expand**

In `Chat.tsx`, change the comparison table to auto-show when 2+ results (remove the toggle, always show):

```tsx
{msg.sourcing.sourcing_results.length >= 2 && (
  <ComparisonTable results={msg.sourcing.sourcing_results} qty={qty} />
)}
```

Remove the `showComparison` state and toggle button.

**Step 8: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 9: Commit**

```bash
git add src/components/sourcing/ResultCard.tsx src/components/sourcing/ComparisonTable.tsx src/pages/Chat.tsx src/lib/api.ts
git commit -m "feat: add reliability gauge, award badges, and auto-expand comparison"
```

---

## Batch 5: Consistency & Responsive (Tasks 13-15)

### Task 13: Sidebar Branding Update & Responsive Collapse

**Files:**
- Modify: `src/components/layout/Sidebar.tsx` (branding + responsive collapse)
- Modify: `src/components/layout/AppLayout.tsx` (responsive sidebar state)

**Step 1: Update sidebar branding**

In `Sidebar.tsx`, change the brand section (lines 65-73):
```tsx
{/* Brand */}
<div className="flex h-16 items-center gap-2.5 border-b border-white/10 px-5">
  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-industrial-400 to-industrial-700 text-sm font-bold text-white shadow-lg">
    I
  </div>
  {!collapsed && (
    <div>
      <p className="text-sm font-montserrat font-bold tracking-wide">IndusAI</p>
      <p className="text-[10px] uppercase tracking-widest text-slate-400">v3.0</p>
    </div>
  )}
</div>
```

Update footer (lines 107-114):
```tsx
{!collapsed && (
  <div className="border-t border-white/10 px-5 py-3">
    <p className="text-[10px] text-slate-500">AI-Powered MRO Platform</p>
    <p className="text-[10px] text-slate-600">Built for Industrial Distribution</p>
  </div>
)}
```

**Step 2: Add collapsed prop and responsive behavior**

Make Sidebar accept a `collapsed` prop and conditionally show labels:

```tsx
interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export default function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
```

When collapsed, hide section labels and nav text, show only icons:
```tsx
{!collapsed && (
  <p className="mb-1.5 px-3 text-[10px] ...">
    {section.label}
  </p>
)}
// ...
<item.icon className="h-[18px] w-[18px] shrink-0" />
{!collapsed && item.label}
```

Change sidebar width: `collapsed ? "w-16" : "w-60"`.

Add a collapse/expand button at the bottom of the nav (visible on lg+ screens):
```tsx
import { ChevronsLeft, ChevronsRight } from "lucide-react";

<button
  onClick={onToggle}
  className="hidden lg:flex items-center justify-center gap-2 mx-3 mb-2 rounded-lg py-2 text-slate-500 hover:bg-white/5 hover:text-white transition-colors"
>
  {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
  {!collapsed && <span className="text-xs">Collapse</span>}
</button>
```

**Step 3: Update AppLayout to manage sidebar state**

In `AppLayout.tsx`, add state for sidebar collapse and pass props:

```tsx
import { useState } from "react";

export default function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <div className={cn("flex flex-1 flex-col transition-all", sidebarCollapsed ? "ml-16" : "ml-60")}>
        <Header />
        <main className="flex-1 p-6">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
```

Add `cn` import and `Sidebar` props.

**Step 4: Add mobile hamburger menu**

On screens < 768px, sidebar should be hidden by default and shown as an overlay when a hamburger button is clicked. Add this to AppLayout:

```tsx
const [mobileOpen, setMobileOpen] = useState(false);

// Mobile overlay
{mobileOpen && (
  <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setMobileOpen(false)} />
)}

// Mobile sidebar (slides in from left)
<div className={cn(
  "lg:hidden fixed inset-y-0 left-0 z-50 transition-transform duration-300",
  mobileOpen ? "translate-x-0" : "-translate-x-full"
)}>
  <Sidebar onToggle={() => setMobileOpen(false)} />
</div>
```

Add a hamburger button in the Header for mobile:
```tsx
// In Header.tsx, add a mobile menu button (visible only on small screens):
<button onClick={onMobileMenuToggle} className="lg:hidden flex h-8 w-8 ...">
  <Menu className="h-5 w-5" />
</button>
```

Pass `onMobileMenuToggle` from AppLayout to Header via context or prop drilling via Outlet context.

**Step 5: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add src/components/layout/Sidebar.tsx src/components/layout/AppLayout.tsx src/components/layout/Header.tsx
git commit -m "feat: responsive sidebar with collapse/expand and mobile hamburger menu"
```

---

### Task 14: Cross-Page Color Unification

**Files:**
- Modify: Multiple page files for color consistency

**Step 1: Audit and fix color usage in each page**

Go through each page file and replace raw Tailwind color classes with the design system palette. Key replacements:

| Raw Class | Replace With | Context |
|-----------|-------------|---------|
| `bg-blue-600`, `text-blue-600` | `bg-industrial-600`, `text-industrial-600` | Buttons, active states |
| `bg-blue-50`, `bg-blue-100` | `bg-industrial-50`, `bg-industrial-100` | Light backgrounds |
| `border-blue-*` | `border-industrial-*` | Borders |
| `bg-emerald-*` | `bg-tech-*` | Success/money indicators |
| `text-gray-*` | `text-neutral-*` or `text-slate-*` | Text (keep slate for consistency) |
| `bg-green-500` | `bg-tech-500` | Status indicators |

Pages to update (in order):
1. `src/pages/Products.tsx` — "industrial-" already used, verify consistency
2. `src/pages/Inventory.tsx` — ReportDownloadButton, tabs
3. `src/pages/Orders.tsx` — status filters, ReportDownloadButton
4. `src/pages/OrderDetail.tsx` — action buttons
5. `src/pages/Quotes.tsx` — table styling
6. `src/pages/Procurement.tsx` — tabs, auto-generate button
7. `src/pages/Invoices.tsx` — tab styling uses "blue-", change to industrial
8. `src/pages/RMA.tsx` — minimal changes needed
9. `src/pages/Channels.tsx` — channel colors (keep semantic for WhatsApp=green, etc.)
10. `src/pages/BulkImport.tsx` — upload button
11. `src/pages/AdminDebug.tsx` — stat card colors
12. `src/pages/Login.tsx` — already uses industrial, verify
13. `src/pages/Signup.tsx` — already uses industrial, verify

**Step 2: Fix table header consistency**

Ensure all page tables use the same header style:
```tsx
<thead>
  <tr className="border-b bg-slate-50/80">
    <th className="whitespace-nowrap px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
```

**Step 3: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 4: Run frontend tests**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm test 2>&1 | tail -10`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/pages/
git commit -m "style: unify color palette across all pages to industrial/tech/neutral"
```

---

### Task 15: Order Confirmation Polish & Final Responsive Fixes

**Files:**
- Modify: `src/pages/Chat.tsx` (order confirmation upgrade)
- Modify: `src/pages/Dashboard.tsx` (responsive grid fixes)

**Step 1: Upgrade order confirmation in chat**

Replace the simple green box (lines 251-260) with an animated confirmation card:

```tsx
{msg.orderConfirmation && (
  <div className="mt-3 animate-scale-in">
    <div className="rounded-xl border border-tech-200 bg-gradient-to-br from-tech-50 to-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-tech-100">
          <CheckCircle2 className="h-6 w-6 text-tech-600" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-800">Order Confirmed</p>
          <p className="text-xs text-slate-500">#{msg.orderConfirmation.order_id}</p>
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-600">{msg.orderConfirmation.message}</p>
    </div>
  </div>
)}
```

**Step 2: Ensure Dashboard grids are responsive**

Verify the Dashboard uses responsive breakpoints for all grid sections. The current implementation already uses `grid-cols-1 sm:grid-cols-2 xl:grid-cols-4` for KPIs and `grid-cols-1 lg:grid-cols-2` for charts, which is correct.

Add responsive classes to the quick actions bar if not already:
```tsx
<div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
```

**Step 3: Add mobile scroll wrapper to all tables**

In pages with tables (Orders, Invoices, Quotes, Procurement, RMA, Channels), ensure the table is inside:
```tsx
<div className="overflow-x-auto">
  <table className="w-full min-w-[600px] text-left text-sm">
    ...
  </table>
</div>
```

The `min-w-[600px]` ensures horizontal scroll on mobile instead of layout breakage.

**Step 4: Input area responsive fix for Chat**

Ensure the chat input area doesn't break on mobile — the input + button layout already uses flexbox which is good. Add `min-w-0` to the input to prevent overflow:
```tsx
<input className="min-w-0 flex-1 ..." />
```

**Step 5: Verify full build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build:dev 2>&1 | tail -5`
Expected: Build succeeds

**Step 6: Run all tests (backend + frontend)**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm test 2>&1 | tail -10`
Expected: All frontend tests pass

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && source .venv/bin/activate && python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: All backend tests pass

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: polish order confirmation, fix responsive layouts across all pages"
```

---

## Post-Implementation Verification

After all 15 tasks are complete, do a full verification:

1. **Build check:** `npm run build` (production build, not dev)
2. **Frontend tests:** `npm test`
3. **Backend tests:** `source .venv/bin/activate && python -m pytest tests/ -x -q`
4. **Visual check list:**
   - [ ] Landing page renders at `/landing` with all sections
   - [ ] Login/Signup still work and redirect to `/dashboard`
   - [ ] Dashboard shows welcome header, quick actions, polished charts
   - [ ] Chat welcome state shows centered hero with suggestions
   - [ ] Chat search shows thinking stages, then typewriter text
   - [ ] Chat dark mode toggle works
   - [ ] Chat side panel opens/closes
   - [ ] Result cards show reliability gauge and badges
   - [ ] Comparison table auto-expands
   - [ ] Sidebar collapse/expand works on desktop
   - [ ] Mobile hamburger menu works on small screens
   - [ ] All pages use consistent color palette
   - [ ] Tables scroll horizontally on mobile

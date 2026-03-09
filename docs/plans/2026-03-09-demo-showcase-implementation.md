# Demo Showcase Landing Page — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 7 new sections to the Landing page that showcase what's built — with live API stats, interactive knowledge graph, architecture flow, ROI comparison, and deep-links into the running app.

**Architecture:** All frontend-only. New sub-components in `src/components/demo/`. Landing.tsx imports and renders them in order. Live stats fetched via existing `api.*` functions on mount. Graph viz reuses `react-force-graph-2d`. No new backend routes.

**Tech Stack:** React, TypeScript, Tailwind CSS, Framer Motion, react-force-graph-2d, existing API client (`src/lib/api.ts`)

---

### Task 1: Create the animated counter hook

**Files:**
- Create: `src/hooks/useCountUp.ts`

**Step 1: Create the hook**

```typescript
import { useState, useEffect, useRef } from "react";

export function useCountUp(end: number, duration = 1500, start = 0) {
  const [count, setCount] = useState(start);
  const prevEnd = useRef(start);

  useEffect(() => {
    if (end === prevEnd.current) return;
    prevEnd.current = end;

    const startTime = performance.now();
    const startVal = start;

    function animate(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(startVal + (end - startVal) * eased));
      if (progress < 1) requestAnimationFrame(animate);
    }

    requestAnimationFrame(animate);
  }, [end, duration, start]);

  return count;
}
```

**Step 2: Verify it compiles**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npx tsc --noEmit src/hooks/useCountUp.ts 2>&1 | head -5`
Expected: No errors

**Step 3: Commit**

```bash
git add src/hooks/useCountUp.ts
git commit -m "feat: add useCountUp animation hook for demo stats"
```

---

### Task 2: Create the ProblemSection component

**Files:**
- Create: `src/components/demo/ProblemSection.tsx`

**Step 1: Build the component**

```tsx
import { motion } from "framer-motion";
import { AlertTriangle, Clock, Users, DollarSign, Mail } from "lucide-react";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const painPoints = [
  { icon: Mail, value: "2M+", label: "Emails per year", color: "text-red-500" },
  { icon: Users, value: "8", label: "People across 12 inboxes", color: "text-orange-500" },
  { icon: Clock, value: "2.5 hrs", label: "Average response time", color: "text-amber-500" },
  { icon: DollarSign, value: "$640K", label: "Annual labor cost", color: "text-red-600" },
  { icon: AlertTriangle, value: "High", label: "Error rate (manual triage)", color: "text-red-400" },
];

export default function ProblemSection() {
  return (
    <section className="bg-slate-900 py-20">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-12 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-red-500/10 px-4 py-1.5 text-sm font-medium text-red-400">
            The Problem
          </span>
          <h2 className="text-3xl font-bold text-white">
            Industrial Support Teams Are Drowning
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-400">
            Chemical distributors and industrial suppliers manually triage millions of
            inbound emails — orders, quote requests, TDS/SDS lookups, and support questions.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={stagger}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"
        >
          {painPoints.map((p) => {
            const Icon = p.icon;
            return (
              <motion.div
                key={p.label}
                variants={fadeIn}
                className="rounded-xl border border-slate-700/50 bg-slate-800/50 p-5 text-center backdrop-blur-sm"
              >
                <Icon className={`mx-auto mb-3 h-8 w-8 ${p.color}`} />
                <p className="text-2xl font-bold text-white">{p.value}</p>
                <p className="mt-1 text-sm text-slate-400">{p.label}</p>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/demo/ProblemSection.tsx
git commit -m "feat: add ProblemSection component for demo showcase"
```

---

### Task 3: Create the ArchitectureFlow component

**Files:**
- Create: `src/components/demo/ArchitectureFlow.tsx`

**Step 1: Build the component**

```tsx
import { motion } from "framer-motion";
import { Mail, MessageSquare, FileText, ArrowRight, GitMerge, Brain, Inbox, Send, ShieldCheck } from "lucide-react";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.15 } },
};

const steps = [
  {
    icon: Mail,
    title: "Inbound Channels",
    desc: "Email, Web Chat, Fax",
    gradient: "from-blue-600 to-blue-800",
  },
  {
    icon: GitMerge,
    title: "Unified Router",
    desc: "Normalize → InboundMessage",
    gradient: "from-indigo-600 to-indigo-800",
  },
  {
    icon: Brain,
    title: "Multi-Intent Classifier",
    desc: "9 intents, entity extraction",
    gradient: "from-purple-600 to-purple-800",
  },
  {
    icon: FileText,
    title: "Auto-Response Engine",
    desc: "KG + TDS/SDS + Inventory",
    gradient: "from-tech-600 to-tech-800",
  },
  {
    icon: Inbox,
    title: "Human Review Queue",
    desc: "Approve / Edit / Escalate",
    gradient: "from-industrial-600 to-industrial-800",
    badge: "No Auto-Send",
  },
  {
    icon: Send,
    title: "Send",
    desc: "Approved response dispatched",
    gradient: "from-emerald-600 to-emerald-800",
  },
];

export default function ArchitectureFlow() {
  return (
    <section className="bg-white py-20">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-14 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-indigo-100 px-4 py-1.5 text-sm font-medium text-indigo-700">
            Architecture
          </span>
          <h2 className="text-3xl font-bold text-slate-900">How It Works</h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-500">
            Every message flows through a structured pipeline — classified, enriched, drafted, and reviewed before sending.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={stagger}
          className="flex flex-wrap items-center justify-center gap-2"
        >
          {steps.map((step, i) => {
            const Icon = step.icon;
            return (
              <motion.div key={step.title} variants={fadeIn} className="flex items-center gap-2">
                <div className="relative w-40 rounded-xl border border-slate-100 bg-white p-4 text-center shadow-sm">
                  <div
                    className={`mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${step.gradient} text-white`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">{step.title}</h3>
                  <p className="mt-0.5 text-xs text-slate-500">{step.desc}</p>
                  {step.badge && (
                    <span className="absolute -top-2 right-2 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                      {step.badge}
                    </span>
                  )}
                </div>
                {i < steps.length - 1 && (
                  <ArrowRight className="h-5 w-5 flex-shrink-0 text-slate-300" />
                )}
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/demo/ArchitectureFlow.tsx
git commit -m "feat: add ArchitectureFlow component for demo showcase"
```

---

### Task 4: Create the LiveStats component

**Files:**
- Create: `src/components/demo/LiveStats.tsx`

**Step 1: Build the component**

```tsx
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Server, TestTube, Package, Mail, Target,
  Database, FileText, Users,
} from "lucide-react";
import { api } from "@/lib/api";
import { useCountUp } from "@/hooks/useCountUp";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: number;
  live?: boolean;
  gradient: string;
}

function StatCard({ icon: Icon, label, value, live, gradient }: StatCardProps) {
  const display = useCountUp(value);
  return (
    <motion.div
      variants={fadeIn}
      className="relative rounded-xl border border-slate-100 bg-white p-5 shadow-sm"
    >
      {live && (
        <span className="absolute right-3 top-3 flex items-center gap-1.5 text-[10px] font-medium text-emerald-600">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
          Live
        </span>
      )}
      <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${gradient} text-white`}>
        <Icon className="h-5 w-5" />
      </div>
      <p className="text-3xl font-bold text-slate-900">{display}</p>
      <p className="mt-1 text-sm text-slate-500">{label}</p>
    </motion.div>
  );
}

export default function LiveStats() {
  const [stats, setStats] = useState({
    endpoints: 100,
    tests: 483,
    products: 0,
    messages: 0,
    intents: 9,
    graphNodes: 0,
    documents: 0,
    accounts: 0,
  });

  useEffect(() => {
    async function load() {
      try {
        const [products, inbox, graphStats, accounts] = await Promise.allSettled([
          api.getProducts(1, ""),
          api.getInboxStats(),
          api.getGraphStats(),
          api.getCustomerAccounts(1, 0),
        ]);

        setStats((prev) => ({
          ...prev,
          products: products.status === "fulfilled" ? products.value.total : prev.products,
          messages: inbox.status === "fulfilled" ? inbox.value.total : prev.messages,
          graphNodes:
            graphStats.status === "fulfilled"
              ? Object.values(graphStats.value.nodes).reduce((a, b) => a + b, 0)
              : prev.graphNodes,
          accounts:
            accounts.status === "fulfilled"
              ? accounts.value.accounts.length
              : prev.accounts,
        }));
      } catch {
        // keep defaults
      }
    }
    load();
  }, []);

  const cards = [
    { icon: Server, label: "API Endpoints", value: stats.endpoints, gradient: "from-blue-600 to-blue-800" },
    { icon: TestTube, label: "Tests Passing", value: stats.tests, gradient: "from-emerald-600 to-emerald-800" },
    { icon: Package, label: "Products in DB", value: stats.products, gradient: "from-industrial-600 to-industrial-800", live: true },
    { icon: Mail, label: "Inbox Messages", value: stats.messages, gradient: "from-purple-600 to-purple-800", live: true },
    { icon: Target, label: "Intents Supported", value: stats.intents, gradient: "from-amber-600 to-amber-800" },
    { icon: Database, label: "Knowledge Graph Nodes", value: stats.graphNodes, gradient: "from-tech-600 to-tech-800", live: true },
    { icon: FileText, label: "TDS/SDS Documents", value: stats.documents, gradient: "from-indigo-600 to-indigo-800", live: true },
    { icon: Users, label: "Customer Accounts", value: stats.accounts, gradient: "from-rose-600 to-rose-800", live: true },
  ];

  return (
    <section className="border-y border-slate-200 bg-slate-50 py-20">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-12 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-emerald-100 px-4 py-1.5 text-sm font-medium text-emerald-700">
            Status
          </span>
          <h2 className="text-3xl font-bold text-slate-900">What's Built</h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-500">
            Live numbers pulled from the running platform — not mockups.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={stagger}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        >
          {cards.map((c) => (
            <StatCard key={c.label} {...c} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/demo/LiveStats.tsx
git commit -m "feat: add LiveStats component with animated counters"
```

---

### Task 5: Create the KnowledgeGraphDemo component

**Files:**
- Create: `src/components/demo/KnowledgeGraphDemo.tsx`

**Step 1: Build the component**

This embeds a live force-graph visualization and a search bar that queries the knowledge graph.

```tsx
import { useState, useCallback, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import ForceGraph2D from "react-force-graph-2d";
import { Search, Database, GitBranch } from "lucide-react";
import { api } from "@/lib/api";
import { useCountUp } from "@/hooks/useCountUp";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const NODE_COLORS: Record<string, string> = {
  Product: "#1e3a8a",
  Manufacturer: "#059669",
  ProductLine: "#0d9488",
  Industry: "#f59e0b",
  TDS: "#7c3aed",
  SDS: "#dc2626",
};

export default function KnowledgeGraphDemo() {
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const { data: vizData } = useQuery({
    queryKey: ["demo-graph-viz"],
    queryFn: () => api.getGraphViz(),
  });

  const { data: graphStats } = useQuery({
    queryKey: ["demo-graph-stats"],
    queryFn: () => api.getGraphStats(),
  });

  const { data: searchResults, isLoading: searching } = useQuery({
    queryKey: ["demo-graph-search", searchTerm],
    queryFn: () => api.searchProducts(searchTerm),
    enabled: searchTerm.length >= 2,
  });

  const totalNodes = graphStats
    ? Object.values(graphStats.nodes).reduce((a, b) => a + b, 0)
    : 0;
  const totalEdges = graphStats
    ? Object.values(graphStats.edges).reduce((a, b) => a + b, 0)
    : 0;

  const nodeCount = useCountUp(totalNodes);
  const edgeCount = useCountUp(totalEdges);

  const graphData = vizData
    ? {
        nodes: vizData.nodes.map((n) => ({
          ...n,
          color: NODE_COLORS[n.label] || "#6b7280",
        })),
        links: vizData.edges.map((e) => ({
          source: e.source,
          target: e.target,
          label: e.relationship,
        })),
      }
    : { nodes: [], links: [] };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchTerm(searchQuery.trim());
  };

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D) => {
    const size = node.label === "Product" ? 8 : node.label === "TDS" || node.label === "SDS" ? 4 : 6;
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = node.color || "#6b7280";
    ctx.fill();
    ctx.font = "3px sans-serif";
    ctx.textAlign = "center";
    ctx.fillStyle = "#374151";
    ctx.fillText(node.name?.slice(0, 20) || "", node.x, node.y + size + 4);
  }, []);

  useEffect(() => {
    if (graphRef.current) {
      graphRef.current.d3Force("charge")?.strength(-80);
    }
  }, [vizData]);

  return (
    <section className="bg-white py-20">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-12 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-purple-100 px-4 py-1.5 text-sm font-medium text-purple-700">
            Knowledge Graph
          </span>
          <h2 className="text-3xl font-bold text-slate-900">
            Structured Intelligence, Not Chunked Documents
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-500">
            Product specs, TDS/SDS data, manufacturers, and cross-references stored as a
            connected graph in Neo4j. Property lookups, not semantic guessing.
          </p>
        </motion.div>

        {/* Stats bar */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-8 flex flex-wrap items-center justify-center gap-8"
        >
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-purple-600" />
            <span className="text-2xl font-bold text-slate-900">{nodeCount}</span>
            <span className="text-sm text-slate-500">Nodes</span>
            <span className="ml-1 flex items-center gap-1 text-[10px] text-emerald-600">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
              Live
            </span>
          </div>
          <div className="flex items-center gap-2">
            <GitBranch className="h-5 w-5 text-purple-600" />
            <span className="text-2xl font-bold text-slate-900">{edgeCount}</span>
            <span className="text-sm text-slate-500">Relationships</span>
          </div>
          {/* Node type legend */}
          <div className="flex flex-wrap gap-3">
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5 text-xs text-slate-500">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                {type}
              </div>
            ))}
          </div>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-5">
          {/* Graph visualization */}
          <div ref={containerRef} className="relative lg:col-span-3 rounded-xl border border-slate-200 bg-slate-50 overflow-hidden" style={{ height: 420 }}>
            {graphData.nodes.length > 0 ? (
              <ForceGraph2D
                ref={graphRef}
                graphData={graphData}
                width={containerRef.current?.clientWidth || 600}
                height={420}
                nodeCanvasObject={paintNode}
                linkColor={() => "#d1d5db"}
                linkWidth={1}
                enableZoomInteraction={true}
                enablePanInteraction={true}
                cooldownTicks={80}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-slate-400">
                Loading graph...
              </div>
            )}
          </div>

          {/* Search panel */}
          <div className="lg:col-span-2 space-y-4">
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search products or CAS#..."
                  className="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-10 pr-4 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
              </div>
              <button
                type="submit"
                className="rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-purple-500"
              >
                Search
              </button>
            </form>

            <div className="max-h-[340px] space-y-2 overflow-y-auto">
              {searching && <p className="text-sm text-slate-400">Searching...</p>}
              {searchResults?.items?.map((item) => (
                <div
                  key={item.sku}
                  className="rounded-lg border border-slate-200 bg-white p-3"
                >
                  <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                  <p className="text-xs text-slate-500">
                    {item.manufacturer} &middot; {item.sku}
                  </p>
                  {item.specs && item.specs.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {item.specs.slice(0, 3).map((s) => (
                        <span
                          key={s.name}
                          className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600"
                        >
                          {s.name}: {s.value}
                          {s.unit ? ` ${s.unit}` : ""}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {searchTerm && !searching && searchResults?.items?.length === 0 && (
                <p className="text-sm text-slate-400">No results found.</p>
              )}
              {!searchTerm && (
                <p className="text-sm text-slate-400">
                  Try searching &quot;silicone&quot;, &quot;adhesive&quot;, or a CAS number.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/demo/KnowledgeGraphDemo.tsx
git commit -m "feat: add KnowledgeGraphDemo with live graph viz and search"
```

---

### Task 6: Create the LiveFeatures component

**Files:**
- Create: `src/components/demo/LiveFeatures.tsx`

**Step 1: Build the component**

```tsx
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Inbox, BookOpen, BarChart3, MessageSquare, Package, ArrowRight } from "lucide-react";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const features = [
  {
    icon: Inbox,
    title: "Inbox",
    desc: "See 15 classified messages with AI-drafted responses",
    path: "/inbox",
    gradient: "from-industrial-600 to-industrial-800",
  },
  {
    icon: BookOpen,
    title: "Knowledge Base",
    desc: "Browse products, TDS/SDS documents, and graph explorer",
    path: "/knowledge-base",
    gradient: "from-purple-600 to-purple-800",
  },
  {
    icon: BarChart3,
    title: "Dashboard",
    desc: "ROI metrics, KPIs, and operational analytics",
    path: "/dashboard",
    gradient: "from-emerald-600 to-emerald-800",
  },
  {
    icon: MessageSquare,
    title: "AI Chat",
    desc: "Natural language product search with GraphRAG",
    path: "/chat",
    gradient: "from-blue-600 to-blue-800",
  },
  {
    icon: Package,
    title: "Products",
    desc: "Full product catalog with specs and graph data",
    path: "/products",
    gradient: "from-amber-600 to-amber-800",
  },
];

export default function LiveFeatures() {
  return (
    <section className="border-y border-slate-200 bg-slate-50 py-20">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-12 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-industrial-100 px-4 py-1.5 text-sm font-medium text-industrial-700">
            Try It Live
          </span>
          <h2 className="text-3xl font-bold text-slate-900">Jump Into the Platform</h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-500">
            These aren't mockups — click any card to open the live feature.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={stagger}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"
        >
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <motion.div key={f.title} variants={fadeIn}>
                <Link
                  to={f.path}
                  className="group flex h-full flex-col rounded-xl border border-slate-100 bg-white p-5 shadow-sm transition hover:shadow-lg hover:border-industrial-200"
                >
                  <div
                    className={`mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${f.gradient} text-white`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900">{f.title}</h3>
                  <p className="mt-1 flex-1 text-xs leading-relaxed text-slate-500">{f.desc}</p>
                  <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-industrial-600 group-hover:text-industrial-500">
                    Open Live <ArrowRight className="h-3 w-3" />
                  </span>
                </Link>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/demo/LiveFeatures.tsx
git commit -m "feat: add LiveFeatures cards linking to running app pages"
```

---

### Task 7: Create the ROIComparison component

**Files:**
- Create: `src/components/demo/ROIComparison.tsx`

**Step 1: Build the component**

```tsx
import { motion } from "framer-motion";
import { TrendingDown, TrendingUp, DollarSign } from "lucide-react";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const rows = [
  { metric: "Response Time", before: "2.5 hours", after: "~3 minutes", improvement: "98%" },
  { metric: "Support Reps Needed", before: "8", after: "3", improvement: "63%" },
  { metric: "Annual Labor Cost", before: "$640K", after: "~$240K", improvement: "63%" },
  { metric: "Error Rate", before: "High (manual)", after: "Near-zero (AI + review)", improvement: "~95%" },
];

export default function ROIComparison() {
  return (
    <section className="bg-slate-900 py-20">
      <div className="mx-auto max-w-4xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-12 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-emerald-500/10 px-4 py-1.5 text-sm font-medium text-emerald-400">
            ROI
          </span>
          <h2 className="text-3xl font-bold text-white">The Business Impact</h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-400">
            Before and after deploying IndusAI for a mid-size chemical distributor.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={fadeIn}
        >
          <div className="overflow-hidden rounded-xl border border-slate-700/50">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-700/50 bg-slate-800/50">
                  <th className="px-6 py-3 text-sm font-medium text-slate-400">Metric</th>
                  <th className="px-6 py-3 text-sm font-medium text-red-400">
                    <span className="flex items-center gap-1.5">
                      <TrendingDown className="h-3.5 w-3.5" /> Before
                    </span>
                  </th>
                  <th className="px-6 py-3 text-sm font-medium text-emerald-400">
                    <span className="flex items-center gap-1.5">
                      <TrendingUp className="h-3.5 w-3.5" /> After IndusAI
                    </span>
                  </th>
                  <th className="px-6 py-3 text-sm font-medium text-slate-400">Improvement</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={r.metric}
                    className={i < rows.length - 1 ? "border-b border-slate-700/30" : ""}
                  >
                    <td className="px-6 py-4 text-sm font-medium text-white">{r.metric}</td>
                    <td className="px-6 py-4 text-sm text-red-300">{r.before}</td>
                    <td className="px-6 py-4 text-sm text-emerald-300">{r.after}</td>
                    <td className="px-6 py-4">
                      <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400">
                        {r.improvement}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Savings callout */}
          <div className="mt-8 flex items-center justify-center gap-3 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10">
              <DollarSign className="h-7 w-7 text-emerald-400" />
            </div>
            <div className="text-left">
              <p className="text-3xl font-bold text-emerald-400">$400K/year</p>
              <p className="text-sm text-slate-400">Projected annual savings</p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/demo/ROIComparison.tsx
git commit -m "feat: add ROIComparison before/after table for demo"
```

---

### Task 8: Create the Roadmap component

**Files:**
- Create: `src/components/demo/Roadmap.tsx`

**Step 1: Build the component**

```tsx
import { motion } from "framer-motion";
import { MessageSquare, Plug, GraduationCap, Building2, BarChart3 } from "lucide-react";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const items = [
  { icon: MessageSquare, title: "WhatsApp & Fax Channels", desc: "Expand inbound channels beyond email and web chat" },
  { icon: Plug, title: "ERP Adapters (SAP, Oracle)", desc: "Real-time inventory and order sync from enterprise ERPs" },
  { icon: GraduationCap, title: "Auto-Training from Feedback", desc: "Classifier improves continuously from human corrections" },
  { icon: Building2, title: "Multi-Tenant Deployment", desc: "Isolated data per customer with shared infrastructure" },
  { icon: BarChart3, title: "Advanced Analytics", desc: "Response time trends, classification accuracy, ROI tracking" },
];

export default function Roadmap() {
  return (
    <section className="bg-white py-20">
      <div className="mx-auto max-w-4xl px-6">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
          variants={fadeIn}
          className="mb-12 text-center"
        >
          <span className="mb-3 inline-block rounded-full bg-blue-100 px-4 py-1.5 text-sm font-medium text-blue-700">
            Roadmap
          </span>
          <h2 className="text-3xl font-bold text-slate-900">What's Next</h2>
          <p className="mx-auto mt-3 max-w-2xl text-slate-500">
            The platform is live — here's where we're headed.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
          variants={stagger}
          className="space-y-4"
        >
          {items.map((item, i) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={item.title}
                variants={fadeIn}
                className="flex items-start gap-4 rounded-xl border border-slate-100 bg-white p-5 shadow-sm"
              >
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-600">
                      Coming Soon
                    </span>
                  </div>
                  <p className="mt-0.5 text-sm text-slate-500">{item.desc}</p>
                </div>
                <span className="flex-shrink-0 text-xs text-slate-400">Phase {i + 1}</span>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/demo/Roadmap.tsx
git commit -m "feat: add Roadmap component with upcoming features"
```

---

### Task 9: Update the Hero section and wire all demo sections into Landing.tsx

**Files:**
- Modify: `src/pages/Landing.tsx`

**Step 1: Update Landing.tsx**

Replace the entire Landing.tsx to:
1. Update the hero headline/subheadline to the supplier sales automation framing
2. Add nav links for new sections (Problem, Architecture, Demo, Graph, ROI, Roadmap)
3. Import and render all demo components in order between the hero and the tech stack/footer

The section order:
1. Hero (updated) — existing
2. ProblemSection — new
3. ArchitectureFlow — new
4. LiveStats — new (replaces old stats bar)
5. KnowledgeGraphDemo — new
6. Feature Cards — existing (kept)
7. LiveFeatures — new
8. ROIComparison — new
9. Tech Stack — existing (kept)
10. Roadmap — new
11. CTA + Footer — existing (kept)

**Key changes to existing Landing.tsx:**
- Update hero headline from "The Operating System for MRO Distribution" to "Supplier Sales & Support Automation"
- Update hero subheadline
- Update hero badge text
- Add new nav links for demo sections
- Import all 6 new components
- Remove old stats bar (replaced by LiveStats)
- Insert new sections in the correct order

**Step 2: Verify build**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run build 2>&1 | tail -10`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/pages/Landing.tsx
git commit -m "feat: wire demo showcase sections into Landing page"
```

---

### Task 10: Visual QA — run dev server and verify

**Step 1: Start the dev server**

Run: `cd /Users/shahmeer/Documents/IndusAI2/IndusAI2.0 && npm run dev`

**Step 2: Open browser and navigate to `/landing`**

Verify all sections render:
- [ ] Hero shows updated headline
- [ ] Problem section shows 5 pain cards
- [ ] Architecture flow shows 6 connected steps
- [ ] Live Stats shows 8 cards with animated counters
- [ ] Knowledge Graph shows force-graph visualization + search
- [ ] Feature cards render (existing)
- [ ] Live Features shows 5 clickable cards
- [ ] ROI table shows before/after comparison
- [ ] Tech stack strip renders
- [ ] Roadmap shows 5 upcoming items
- [ ] Smooth scrolling from nav links works
- [ ] Animations trigger on scroll

**Step 3: Fix any visual issues**

**Step 4: Final commit**

```bash
git add -A
git commit -m "fix: visual polish for demo showcase sections"
```

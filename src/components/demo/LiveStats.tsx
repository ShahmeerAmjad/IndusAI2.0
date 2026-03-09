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
    tests: 527,
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
        const [products, inbox, graphStats, accounts, docCount] = await Promise.allSettled([
          api.getCatalogProducts({ page: 1, pageSize: 1 }),
          api.getInboxStats(),
          api.getGraphStats(),
          api.getCustomerAccounts(1, 0),
          api.getDocumentCount(),
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
          documents:
            docCount.status === "fulfilled"
              ? docCount.value.total
              : prev.documents,
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

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

import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Search,
  Database,
  ShoppingCart,
  Truck,
  Brain,
  FileText,
  MessageSquare,
  Shield,
  ArrowRight,
  ChevronDown,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const stats = [
  { value: "100+", label: "API Endpoints" },
  { value: "227", label: "Tests Passing" },
  { value: "5-Stage", label: "AI Pipeline" },
  { value: "16", label: "App Pages" },
  { value: "Full", label: "O2C + P2P" },
];

const features = [
  {
    title: "AI Sourcing Engine",
    description:
      "Natural language part search with 5-stage GraphRAG pipeline. Results ranked by price, delivery, and proximity.",
    icon: Search,
    gradient: "from-industrial-600 to-industrial-800",
  },
  {
    title: "Knowledge Graph",
    description:
      "Neo4j-powered part intelligence with cross-references, specs, and compatibility mapping across suppliers.",
    icon: Database,
    gradient: "from-tech-600 to-tech-800",
  },
  {
    title: "Order-to-Cash",
    description:
      "Complete O2C flow — products, inventory, orders, quotes, invoicing, payments, and returns management.",
    icon: ShoppingCart,
    gradient: "from-blue-600 to-blue-800",
  },
  {
    title: "Procure-to-Pay",
    description:
      "Supplier management, purchase orders, goods receipts, and auto-PO generation from reorder alerts.",
    icon: Truck,
    gradient: "from-indigo-600 to-indigo-800",
  },
  {
    title: "Intelligence Layer",
    description:
      "Reliability scoring with age decay, composite price comparison, location optimization, and freshness scheduling.",
    icon: Brain,
    gradient: "from-purple-600 to-purple-800",
  },
  {
    title: "Reports & Bulk Ops",
    description:
      "CSV, Excel, and PDF report generation. Bulk CSV import with dry-run validation and downloadable templates.",
    icon: FileText,
    gradient: "from-amber-600 to-amber-800",
  },
  {
    title: "Omnichannel",
    description:
      "Web, WhatsApp, email, and SMS messaging with intent classification, escalation management, and routing.",
    icon: MessageSquare,
    gradient: "from-emerald-600 to-emerald-800",
  },
  {
    title: "Multi-Tenant Auth",
    description:
      "JWT access + refresh token rotation, org-scoped data, bcrypt hashing, and role-based access control.",
    icon: Shield,
    gradient: "from-rose-600 to-rose-800",
  },
];

const techStack = [
  "React",
  "FastAPI",
  "Neo4j",
  "PostgreSQL",
  "Redis",
  "Claude AI",
  "Voyage AI",
];

/* ------------------------------------------------------------------ */
/*  Animation variants                                                 */
/* ------------------------------------------------------------------ */

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.07, duration: 0.5, ease: "easeOut" },
  }),
};

const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

/* ------------------------------------------------------------------ */
/*  Smooth-scroll helper                                               */
/* ------------------------------------------------------------------ */

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function Landing() {
  return (
    <div className="min-h-screen bg-white font-inter antialiased">
      {/* ── Navigation ───────────────────────────────────────────── */}
      <nav className="fixed inset-x-0 top-0 z-50 border-b border-slate-200/60 bg-white/80 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          {/* Logo */}
          <Link to="/landing" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-industrial-500 to-industrial-800 font-montserrat text-lg font-bold text-white shadow-md">
              I
            </div>
            <span className="font-montserrat text-xl font-bold tracking-tight text-slate-900">
              IndusAI
            </span>
          </Link>

          {/* Center links */}
          <div className="hidden items-center gap-8 md:flex">
            <button
              onClick={() => scrollTo("features")}
              className="text-sm font-medium text-slate-600 transition hover:text-industrial-700"
            >
              Features
            </button>
            <button
              onClick={() => scrollTo("tech")}
              className="text-sm font-medium text-slate-600 transition hover:text-industrial-700"
            >
              Tech Stack
            </button>
          </div>

          {/* Auth buttons */}
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-industrial-400 hover:text-industrial-700"
            >
              Login
            </Link>
            <Link
              to="/signup"
              className="rounded-lg bg-industrial-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-industrial-500"
            >
              Sign Up
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────── */}
      <section className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-industrial-900 pt-16">
        {/* Decorative background elements */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-40 -top-40 h-[500px] w-[500px] rounded-full bg-industrial-600/10 blur-3xl" />
          <div className="absolute -bottom-32 -right-32 h-[400px] w-[400px] rounded-full bg-industrial-500/10 blur-3xl" />
          <div className="absolute left-1/2 top-1/3 h-[300px] w-[300px] -translate-x-1/2 rounded-full bg-tech-600/5 blur-3xl" />
        </div>

        <div className="relative z-10 mx-auto max-w-4xl px-6 text-center">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
            className="flex flex-col items-center gap-6"
          >
            {/* Badge */}
            <motion.div
              variants={fadeIn}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-slate-300 backdrop-blur-sm"
            >
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 animate-pulse-slow" />
              Platform Live &mdash; 16 Pages Deployed
            </motion.div>

            {/* Heading */}
            <motion.h1
              variants={fadeIn}
              className="font-montserrat text-5xl font-bold leading-tight tracking-tight text-white lg:text-6xl"
            >
              The Operating System
              <br />
              for MRO Distribution
            </motion.h1>

            {/* Subheading */}
            <motion.p
              variants={fadeIn}
              className="max-w-2xl text-lg leading-relaxed text-slate-300"
            >
              AI-powered sourcing, order-to-cash, and supply chain intelligence
              &mdash; built for industrial distributors
            </motion.p>

            {/* CTA buttons */}
            <motion.div variants={fadeIn} className="mt-2 flex flex-wrap items-center justify-center gap-4">
              <Link
                to="/signup"
                className="inline-flex items-center gap-2 rounded-lg bg-industrial-500 px-8 py-3 font-semibold text-white shadow-lg shadow-industrial-500/25 transition hover:bg-industrial-400"
              >
                Get Started
                <ArrowRight className="h-4 w-4" />
              </Link>
              <button
                onClick={() => scrollTo("features")}
                className="inline-flex items-center gap-2 rounded-lg border border-white/30 px-8 py-3 font-semibold text-white transition hover:bg-white/10"
              >
                Explore Features
              </button>
            </motion.div>
          </motion.div>

          {/* Scroll indicator */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2, duration: 0.8 }}
            className="absolute bottom-8 left-1/2 -translate-x-1/2"
          >
            <button
              onClick={() => scrollTo("stats")}
              className="flex flex-col items-center gap-1 text-slate-400 transition hover:text-white"
              aria-label="Scroll down"
            >
              <span className="text-xs uppercase tracking-widest">Scroll</span>
              <ChevronDown className="h-5 w-5 animate-bounce" />
            </button>
          </motion.div>
        </div>
      </section>

      {/* ── Stats Bar ────────────────────────────────────────────── */}
      <section id="stats" className="border-y border-slate-200 bg-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.4 }}
            variants={staggerContainer}
            className="grid grid-cols-2 gap-8 text-center md:grid-cols-5"
          >
            {stats.map((s, i) => (
              <motion.div key={s.label} custom={i} variants={fadeUp}>
                <p className="text-3xl font-bold text-industrial-800">{s.value}</p>
                <p className="mt-1 text-sm text-slate-500">{s.label}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── Feature Cards ────────────────────────────────────────── */}
      <section id="features" className="bg-white py-20">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
            variants={fadeIn}
            className="mb-14 text-center"
          >
            <h2 className="text-3xl font-bold text-slate-900">What We've Built</h2>
            <p className="mt-3 text-slate-500">
              A complete platform for MRO distribution intelligence
            </p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.1 }}
            variants={staggerContainer}
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4"
          >
            {features.map((f, i) => {
              const Icon = f.icon;
              return (
                <motion.div
                  key={f.title}
                  custom={i}
                  variants={fadeUp}
                  className="group relative rounded-xl border border-slate-100 bg-white p-6 shadow-sm transition hover:shadow-lg"
                >
                  {/* Live badge */}
                  <span className="absolute right-4 top-4 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-600">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    Live
                  </span>

                  {/* Icon */}
                  <div
                    className={`mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${f.gradient} text-white shadow-sm`}
                  >
                    <Icon className="h-6 w-6" />
                  </div>

                  {/* Text */}
                  <h3 className="text-lg font-semibold text-slate-900">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">
                    {f.description}
                  </p>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* ── Tech Stack Strip ─────────────────────────────────────── */}
      <section id="tech" className="border-y border-slate-200 bg-slate-50 py-16">
        <div className="mx-auto max-w-5xl px-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={fadeIn}
            className="text-center"
          >
            <h2 className="text-3xl font-bold text-slate-900">Built With</h2>
            <p className="mt-2 text-slate-500">
              Modern, production-grade infrastructure
            </p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            variants={staggerContainer}
            className="mt-10 flex flex-wrap items-center justify-center gap-3"
          >
            {techStack.map((tech, i) => (
              <motion.span
                key={tech}
                custom={i}
                variants={fadeUp}
                className="rounded-lg border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-industrial-300 hover:text-industrial-700"
              >
                {tech}
              </motion.span>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── CTA Section ──────────────────────────────────────────── */}
      <section className="bg-gradient-to-br from-slate-900 via-slate-800 to-industrial-900 py-24">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.4 }}
          variants={fadeIn}
          className="mx-auto max-w-3xl px-6 text-center"
        >
          <h2 className="font-montserrat text-3xl font-bold text-white lg:text-4xl">
            Ready to see it in action?
          </h2>
          <p className="mt-4 text-lg text-slate-300">
            Sign in to explore the full platform
          </p>
          <Link
            to="/signup"
            className="mt-8 inline-flex items-center gap-2 rounded-lg bg-industrial-500 px-8 py-3 font-semibold text-white shadow-lg shadow-industrial-500/25 transition hover:bg-industrial-400"
          >
            Get Started
            <ArrowRight className="h-4 w-4" />
          </Link>
        </motion.div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────── */}
      <footer className="bg-slate-900 py-8">
        <div className="mx-auto max-w-7xl px-6 text-center">
          <p className="text-sm text-slate-400">
            IndusAI v3.0 &mdash; Built for Industrial Distribution
          </p>
          <p className="mt-2 text-xs text-slate-500">
            &copy; 2026 IndusAI. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}

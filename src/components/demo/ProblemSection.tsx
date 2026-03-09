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

import { motion } from "framer-motion";
import { Mail, MessageSquare, FileText, ArrowRight, GitMerge, Brain, Inbox, Send } from "lucide-react";

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
    desc: "Normalize \u2192 InboundMessage",
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

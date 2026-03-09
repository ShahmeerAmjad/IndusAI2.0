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

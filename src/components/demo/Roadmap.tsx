import { motion } from "framer-motion";
import { MessageSquare, Plug, GraduationCap, Building2, BarChart3, Unplug, Cloud, ScanSearch } from "lucide-react";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const items = [
  { icon: Unplug, title: "Zero-Cost Web Scraping", desc: "Migrate from Firecrawl SaaS to open-source Crawl4AI + Playwright — eliminate per-page API costs entirely", badge: "Up Next" },
  { icon: Cloud, title: "Cloud Document Storage (R2)", desc: "Move PDF storage from local disk to Cloudflare R2 — zero egress, CDN-backed, ~$0.15/mo for 10K products", badge: "Coming Soon" },
  { icon: ScanSearch, title: "OCR Pipeline", desc: "Add Tesseract/Google Doc AI for scanned PDFs — cheaper alternative to LLM extraction at volume", badge: "Coming Soon" },
  { icon: MessageSquare, title: "WhatsApp & Fax Channels", desc: "Expand inbound channels beyond email and web chat", badge: "Coming Soon" },
  { icon: Plug, title: "ERP Adapters (SAP, Oracle)", desc: "Real-time inventory and order sync from enterprise ERPs", badge: "Coming Soon" },
  { icon: GraduationCap, title: "Auto-Training from Feedback", desc: "Classifier improves continuously from human corrections", badge: "Coming Soon" },
  { icon: Building2, title: "Multi-Tenant Deployment", desc: "Isolated data per customer with shared infrastructure", badge: "Coming Soon" },
  { icon: BarChart3, title: "Advanced Analytics", desc: "Response time trends, classification accuracy, ROI tracking", badge: "Coming Soon" },
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
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${item.badge === "Up Next" ? "bg-amber-50 text-amber-700" : "bg-blue-50 text-blue-600"}`}>
                      {item.badge}
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

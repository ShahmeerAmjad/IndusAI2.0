import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Database, GitBranch } from "lucide-react";
import { api } from "@/lib/api";
import { useCountUp } from "@/hooks/useCountUp";
import { NODE_COLORS } from "@/hooks/useGraphData";
import SigmaGraph from "@/components/graph/SigmaGraph";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } },
};

export default function KnowledgeGraphDemo() {
  const { data: graphStats } = useQuery({
    queryKey: ["demo-graph-stats"],
    queryFn: () => api.getGraphStats(),
  });

  const totalNodes = graphStats
    ? Object.values(graphStats.nodes).reduce((a, b) => a + b, 0)
    : 0;
  const totalEdges = graphStats
    ? Object.values(graphStats.edges).reduce((a, b) => a + b, 0)
    : 0;

  const nodeCount = useCountUp(totalNodes);
  const edgeCount = useCountUp(totalEdges);

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
          <div className="flex flex-wrap gap-3">
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-1.5 text-xs text-slate-500">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                {type}
              </div>
            ))}
          </div>
        </motion.div>

        {/* Graph */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={fadeIn}
        >
          <SigmaGraph defaultDarkMode={true} height="450px" />
        </motion.div>
      </div>
    </section>
  );
}

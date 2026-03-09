import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import SigmaGraph from "@/components/graph/SigmaGraph";

export default function GraphFullScreen() {
  const navigate = useNavigate();

  return (
    <div className="fixed inset-0 z-50 bg-slate-900">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="absolute left-4 top-4 z-50 flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-2 text-sm text-slate-300 shadow-lg backdrop-blur-sm transition hover:bg-slate-800"
      >
        <ArrowLeft size={16} />
        Back
      </button>

      <SigmaGraph defaultDarkMode={true} height="100vh" />
    </div>
  );
}

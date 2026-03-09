import { ZoomIn, ZoomOut, Maximize2, Sun, Moon, RotateCcw } from "lucide-react";

interface GraphControlsProps {
  darkMode: boolean;
  onToggleDarkMode: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitToScreen: () => void;
  onRestartLayout: () => void;
}

export default function GraphControls({
  darkMode,
  onToggleDarkMode,
  onZoomIn,
  onZoomOut,
  onFitToScreen,
  onRestartLayout,
}: GraphControlsProps) {
  const bg = darkMode
    ? "bg-slate-900/80 border-slate-700"
    : "bg-white/90 border-slate-200";
  const text = darkMode ? "text-slate-300" : "text-slate-600";
  const hoverBg = darkMode ? "hover:bg-slate-800" : "hover:bg-slate-100";

  const buttons = [
    { icon: ZoomIn, label: "Zoom in", onClick: onZoomIn },
    { icon: ZoomOut, label: "Zoom out", onClick: onZoomOut },
    { icon: Maximize2, label: "Fit to screen", onClick: onFitToScreen },
    { icon: RotateCcw, label: "Restart layout", onClick: onRestartLayout },
    {
      icon: darkMode ? Sun : Moon,
      label: darkMode ? "Light mode" : "Dark mode",
      onClick: onToggleDarkMode,
    },
  ];

  return (
    <div
      className={`absolute bottom-4 right-4 z-30 flex flex-col gap-1 rounded-xl border p-1.5 shadow-lg backdrop-blur-sm ${bg}`}
    >
      {buttons.map(({ icon: Icon, label, onClick }) => (
        <button
          key={label}
          onClick={onClick}
          title={label}
          className={`rounded-lg p-2 transition ${text} ${hoverBg}`}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}

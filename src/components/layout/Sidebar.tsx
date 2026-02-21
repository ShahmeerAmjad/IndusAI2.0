import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "📊" },
  { to: "/products", label: "Products", icon: "📦" },
  { to: "/inventory", label: "Inventory", icon: "🏭" },
  { to: "/orders", label: "Orders", icon: "📋" },
  { to: "/quotes", label: "Quotes", icon: "💬" },
  { to: "/procurement", label: "Procurement", icon: "🚚" },
  { to: "/invoices", label: "Invoicing", icon: "💰" },
  { to: "/rma", label: "Returns", icon: "🔄" },
  { to: "/chat", label: "AI Assistant", icon: "🤖" },
];

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-[hsl(var(--sidebar-background))] text-[hsl(var(--sidebar-foreground))]">
      {/* Brand */}
      <div className="flex h-16 items-center gap-2 border-b border-white/10 px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-400 to-blue-600 text-sm font-bold text-white">
          M
        </div>
        <div>
          <p className="text-sm font-montserrat font-bold tracking-wide">MRO Platform</p>
          <p className="text-[10px] uppercase tracking-widest text-slate-400">v3.0</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-[hsl(var(--sidebar-accent))] text-white"
                  : "text-slate-400 hover:bg-white/5 hover:text-white"
              )
            }
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-white/10 px-5 py-3">
        <p className="text-[10px] text-slate-500">
          Agentic Back-Office OS
        </p>
        <p className="text-[10px] text-slate-600">
          Industrial MRO Distribution
        </p>
      </div>
    </aside>
  );
}

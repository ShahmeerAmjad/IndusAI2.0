import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Package,
  Warehouse,
  ClipboardList,
  MessageSquareQuote,
  Truck,
  Receipt,
  RotateCcw,
  Bot,
  Radio,
  Bug,
  Upload,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavSection {
  label: string;
  items: Array<{ to: string; label: string; icon: LucideIcon }>;
}

const NAV_SECTIONS: NavSection[] = [
  {
    label: "Back-Office",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { to: "/products", label: "Products", icon: Package },
      { to: "/inventory", label: "Inventory", icon: Warehouse },
      { to: "/orders", label: "Orders", icon: ClipboardList },
      { to: "/quotes", label: "Quotes", icon: MessageSquareQuote },
      { to: "/procurement", label: "Procurement", icon: Truck },
      { to: "/invoices", label: "Invoicing", icon: Receipt },
      { to: "/rma", label: "Returns", icon: RotateCcw },
    ],
  },
  {
    label: "Front-Office",
    items: [
      { to: "/channels", label: "Channels", icon: Radio },
      { to: "/chat", label: "AI Assistant", icon: Bot },
    ],
  },
  {
    label: "Admin",
    items: [
      { to: "/bulk-import", label: "Bulk Import", icon: Upload },
      { to: "/admin", label: "Debug View", icon: Bug },
    ],
  },
];

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export default function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 flex flex-col bg-[hsl(var(--sidebar-background))] text-[hsl(var(--sidebar-foreground))] transition-all duration-300",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Brand */}
      <div className="flex h-16 items-center gap-2.5 border-b border-white/10 px-5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-industrial-400 to-industrial-700 text-sm font-bold text-white shadow-lg">
          I
        </div>
        {!collapsed && (
          <div>
            <p className="text-sm font-montserrat font-bold tracking-wide">IndusAI</p>
            <p className="text-[10px] uppercase tracking-widest text-slate-400">v3.0</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-4">
            {!collapsed && (
              <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/dashboard"}
                  title={item.label}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                      collapsed && "justify-center px-2",
                      isActive
                        ? "bg-[hsl(var(--sidebar-accent))] text-white"
                        : "text-slate-400 hover:bg-white/5 hover:text-white"
                    )
                  }
                >
                  <item.icon className="h-[18px] w-[18px] shrink-0" />
                  {!collapsed && item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        className="mx-3 mb-2 hidden lg:flex items-center justify-center gap-2 rounded-lg py-2 text-slate-500 hover:bg-white/5 hover:text-white transition-colors"
      >
        {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
        {!collapsed && <span className="text-xs">Collapse</span>}
      </button>

      {/* Footer */}
      {!collapsed && (
        <div className="border-t border-white/10 px-5 py-3">
          <p className="text-[10px] text-slate-500">AI-Powered MRO Platform</p>
          <p className="text-[10px] text-slate-600">Built for Industrial Distribution</p>
        </div>
      )}
    </aside>
  );
}

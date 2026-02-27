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
      { to: "/", label: "Dashboard", icon: LayoutDashboard },
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
      { to: "/admin", label: "Debug View", icon: Bug },
    ],
  },
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
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="mb-4">
            <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => (
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
                  <item.icon className="h-[18px] w-[18px] shrink-0" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
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

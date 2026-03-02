import { useLocation } from "react-router-dom";
import { Bell, LogOut, User, Menu } from "lucide-react";
import { useAuth } from "@/lib/auth";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/products": "Product Catalog",
  "/inventory": "Inventory Management",
  "/orders": "Order Management",
  "/quotes": "Quotes",
  "/procurement": "Procurement",
  "/invoices": "Invoicing & Payments",
  "/rma": "Returns & RMA",
  "/channels": "Omnichannel Hub",
  "/chat": "AI Sourcing Assistant",
  "/bulk-import": "Bulk Import",
  "/admin": "Admin Debug View",
};

interface HeaderProps {
  onMenuToggle?: () => void;
}

export default function Header({ onMenuToggle }: HeaderProps) {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();
  const baseRoute = "/" + (pathname.split("/")[1] || "");
  const title = PAGE_TITLES[baseRoute] || "MRO Platform";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-white/80 px-6 backdrop-blur">
      <div className="flex items-center gap-3">
        {onMenuToggle && (
          <button
            onClick={onMenuToggle}
            className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <h1 className="text-lg font-semibold text-slate-800">{title}</h1>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
          <span className="text-xs text-slate-500">System Online</span>
        </div>
        <button className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
          <Bell className="h-4 w-4" />
        </button>
        {user && (
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-industrial-100 text-industrial-700">
              <User className="h-4 w-4" />
            </div>
            <div className="hidden sm:block">
              <p className="text-xs font-medium text-slate-700 leading-tight">{user.name}</p>
              <p className="text-[10px] text-slate-400 leading-tight">{user.org_name}</p>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

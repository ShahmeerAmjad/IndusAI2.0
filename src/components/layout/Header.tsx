import { useLocation } from "react-router-dom";
import { Bell, User } from "lucide-react";

const PAGE_TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/products": "Product Catalog",
  "/inventory": "Inventory Management",
  "/orders": "Order Management",
  "/quotes": "Quotes",
  "/procurement": "Procurement",
  "/invoices": "Invoicing & Payments",
  "/rma": "Returns & RMA",
  "/channels": "Omnichannel Hub",
  "/chat": "AI Assistant",
};

export default function Header() {
  const { pathname } = useLocation();
  const baseRoute = "/" + (pathname.split("/")[1] || "");
  const title = PAGE_TITLES[baseRoute] || "MRO Platform";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-white/80 px-6 backdrop-blur">
      <div>
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
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-slate-500">
          <User className="h-4 w-4" />
        </div>
      </div>
    </header>
  );
}

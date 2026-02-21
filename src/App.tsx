import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import AppLayout from "@/components/layout/AppLayout";

const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Products = lazy(() => import("@/pages/Products"));
const ProductDetail = lazy(() => import("@/pages/ProductDetail"));
const Inventory = lazy(() => import("@/pages/Inventory"));
const Orders = lazy(() => import("@/pages/Orders"));
const OrderDetail = lazy(() => import("@/pages/OrderDetail"));
const Quotes = lazy(() => import("@/pages/Quotes"));
const Procurement = lazy(() => import("@/pages/Procurement"));
const Invoices = lazy(() => import("@/pages/Invoices"));
const RMA = lazy(() => import("@/pages/RMA"));
const Chat = lazy(() => import("@/pages/Chat"));

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-slate-800" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Suspense fallback={<PageLoader />}><Dashboard /></Suspense>} />
          <Route path="/products" element={<Suspense fallback={<PageLoader />}><Products /></Suspense>} />
          <Route path="/products/:id" element={<Suspense fallback={<PageLoader />}><ProductDetail /></Suspense>} />
          <Route path="/inventory" element={<Suspense fallback={<PageLoader />}><Inventory /></Suspense>} />
          <Route path="/orders" element={<Suspense fallback={<PageLoader />}><Orders /></Suspense>} />
          <Route path="/orders/:id" element={<Suspense fallback={<PageLoader />}><OrderDetail /></Suspense>} />
          <Route path="/quotes" element={<Suspense fallback={<PageLoader />}><Quotes /></Suspense>} />
          <Route path="/procurement" element={<Suspense fallback={<PageLoader />}><Procurement /></Suspense>} />
          <Route path="/invoices" element={<Suspense fallback={<PageLoader />}><Invoices /></Suspense>} />
          <Route path="/rma" element={<Suspense fallback={<PageLoader />}><RMA /></Suspense>} />
          <Route path="/chat" element={<Suspense fallback={<PageLoader />}><Chat /></Suspense>} />
        </Route>
      </Routes>
      <Toaster position="top-right" richColors />
    </BrowserRouter>
  );
}

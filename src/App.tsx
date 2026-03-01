import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
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
const Channels = lazy(() => import("@/pages/Channels"));
const Chat = lazy(() => import("@/pages/Chat"));
const Sourcing = lazy(() => import("@/pages/Sourcing"));
const Login = lazy(() => import("@/pages/Login"));
const Signup = lazy(() => import("@/pages/Signup"));
const AdminDebug = lazy(() => import("@/pages/AdminDebug"));
const BulkImport = lazy(() => import("@/pages/BulkImport"));

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-slate-800" />
    </div>
  );
}

function FullPageLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-industrial-600" />
    </div>
  );
}

function RequireAuth() {
  const { user, isLoading } = useAuth();

  if (isLoading) return <FullPageLoader />;
  if (!user) return <Navigate to="/login" replace />;

  return <Outlet />;
}

function PublicOnly() {
  const { user, isLoading } = useAuth();

  if (isLoading) return <FullPageLoader />;
  if (user) return <Navigate to="/" replace />;

  return <Outlet />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public auth routes */}
          <Route element={<PublicOnly />}>
            <Route path="/login" element={<Suspense fallback={<FullPageLoader />}><Login /></Suspense>} />
            <Route path="/signup" element={<Suspense fallback={<FullPageLoader />}><Signup /></Suspense>} />
          </Route>

          {/* Protected app routes */}
          <Route element={<RequireAuth />}>
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
              <Route path="/channels" element={<Suspense fallback={<PageLoader />}><Channels /></Suspense>} />
              <Route path="/chat" element={<Suspense fallback={<PageLoader />}><Chat /></Suspense>} />
              <Route path="/sourcing" element={<Suspense fallback={<PageLoader />}><Sourcing /></Suspense>} />
              <Route path="/bulk-import" element={<Suspense fallback={<PageLoader />}><BulkImport /></Suspense>} />
              <Route path="/admin" element={<Suspense fallback={<PageLoader />}><AdminDebug /></Suspense>} />
            </Route>
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </BrowserRouter>
  );
}

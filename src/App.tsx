import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Products from "@/pages/Products";
import ProductDetail from "@/pages/ProductDetail";
import Inventory from "@/pages/Inventory";
import Orders from "@/pages/Orders";
import OrderDetail from "@/pages/OrderDetail";
import Quotes from "@/pages/Quotes";
import Procurement from "@/pages/Procurement";
import Invoices from "@/pages/Invoices";
import RMA from "@/pages/RMA";
import Chat from "@/pages/Chat";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:id" element={<ProductDetail />} />
          <Route path="/inventory" element={<Inventory />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/orders/:id" element={<OrderDetail />} />
          <Route path="/quotes" element={<Quotes />} />
          <Route path="/procurement" element={<Procurement />} />
          <Route path="/invoices" element={<Invoices />} />
          <Route path="/rma" element={<RMA />} />
          <Route path="/chat" element={<Chat />} />
        </Route>
      </Routes>
      <Toaster position="top-right" richColors />
    </BrowserRouter>
  );
}

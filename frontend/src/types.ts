export type Role = "admin" | "user";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface Client {
  id: number;
  full_name: string;
  name_normalized: string;
  whatsapp: string | null;
  created_by_id: number;
  created_at: string;
}

export interface ClientInput {
  full_name: string;
  whatsapp?: string | null;
}

export type SaleStatus = "paid" | "pending";

export interface SaleItem {
  id: number;
  sale_id: number;
  product_name: string;
  quantity: number;
  unit_price: string;
  subtotal: string;
}

export interface Sale {
  id: number;
  client_id: number;
  user_id: number;
  sale_date: string;
  status: SaleStatus;
  total: string;
  amount_paid: string;
  remaining: string;
  due_date: string | null;
  created_at: string;
  items: SaleItem[];
}

export interface SaleItemInput {
  product_name: string;
  quantity: number;
  unit_price: number;
}

export interface SaleInput {
  client_id: number;
  sale_date: string;
  status: SaleStatus;
  due_date: string | null;
  items: SaleItemInput[];
}

export interface Dashboard {
  total_clients: number;
  total_sales: number;
  revenue_paid: number;
  revenue_pending: number;
  revenue_month: number;
  pending_count: number;
  overdue_count: number;
  recent_sales: RecentSale[];
  top_products: TopProduct[];
}

export interface RecentSale {
  id: number;
  client_id: number;
  client_name: string;
  sale_date: string;
  status: SaleStatus;
  total: number;
}

export interface TopProduct {
  product_name: string;
  total_quantity: number;
  total_revenue: number;
}

export interface SalesReport {
  period: { start: string; end: string };
  sales_count: number;
  total: number;
  paid_total: number;
  pending_total: number;
  sales: RecentSale[];
}

export interface ClientReportRow {
  client_id: number;
  client_name: string;
  sales_count: number;
  total_revenue: number;
}

export interface ProductReportRow {
  product_name: string;
  total_quantity: number;
  total_revenue: number;
}
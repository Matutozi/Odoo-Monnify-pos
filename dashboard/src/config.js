// Where the dashboard reads its data from.
//
// Point these at your Odoo instance. API_TOKEN must match the
// `monnify_base.dashboard_token` system parameter set in Odoo
// (Settings > Technical > System Parameters).
//
// Override at build/run time with VITE_API_URL / VITE_API_TOKEN if you like.
export const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8069/monnify/dashboard/data";

export const API_TOKEN = import.meta.env.VITE_API_TOKEN || "monnify-demo";

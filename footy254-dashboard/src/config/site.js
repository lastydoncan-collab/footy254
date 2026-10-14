// Public contact details shown on the Home page. Set them in
// footy254-dashboard/.env (see .env.example) - anything left empty is hidden.
export const SITE = {
  supportEmail: import.meta.env.VITE_SUPPORT_EMAIL || "",
  supportPhone: import.meta.env.VITE_SUPPORT_PHONE || "",
  whatsapp: import.meta.env.VITE_SUPPORT_WHATSAPP || "", // digits with country code, e.g. 254712345678
  supportHours: import.meta.env.VITE_SUPPORT_HOURS || "Mon-Fri, 8am-6pm EAT",
};

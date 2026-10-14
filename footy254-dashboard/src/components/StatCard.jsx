import { motion } from "framer-motion";

export default function StatCard({ title, value, subtitle, color = "#f2545b", icon }) {
  return (
    <motion.div
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.2 }}
      className="rounded-[22px] border border-white/10 bg-pitch p-4 shadow-lg"
    >
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold text-slate-400">{title}</p>
        {icon && <div style={{ color }}>{icon}</div>}
      </div>
      <h2 className="text-2xl font-black" style={{ color }}>
        {value}
      </h2>
      {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
    </motion.div>
  );
}

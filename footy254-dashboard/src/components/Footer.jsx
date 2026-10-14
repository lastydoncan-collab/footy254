import { Link } from "react-router-dom";

const links = [
  { to: "/predictions", label: "Predictions" },
  { to: "/live", label: "Live matches" },
  { to: "/analytics", label: "Analytics" },
  { to: "/subscriptions", label: "Premium" },
  { to: "/security", label: "Security" },
  { to: "/settings", label: "Settings" },
];

export default function Footer() {
  return (
    <footer className="mt-12 border-t border-white/10 bg-pitch/60 lg:pl-28">
      <div className="mx-auto max-w-md px-4 py-8 sm:max-w-2xl lg:max-w-6xl">
        <div className="grid gap-8 sm:grid-cols-2">
          <div>
            <p className="font-display font-display-italic text-xl text-chalk">
              FOOTY<span className="text-signal">254</span>
            </p>
            <p className="mt-2 max-w-xs text-sm leading-6 text-chalk/70">
              AI match analysis and predictions for the top leagues, built in Nairobi.
            </p>
          </div>
          <nav aria-label="Footer">
            <ul className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              {links.map((l) => (
                <li key={l.to}>
                  <Link to={l.to} className="text-chalk/80 hover:text-chalk hover:underline">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <p className="mt-8 border-t border-white/10 pt-4 text-xs leading-5 text-chalk/60">
          Predictions are statistical estimates, not guarantees. You must be 18 or older to bet.
          Gamble responsibly.
        </p>
        <p className="mt-2 text-xs text-chalk/50">© {new Date().getFullYear()} FOOTY254 AI</p>
      </div>
      <div className="flag-stripe" aria-hidden="true" />
    </footer>
  );
}

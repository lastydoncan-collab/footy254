import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Users, CalendarDays, Radio, Clock3, Brain, Gauge, Bell, ChevronDown } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { getTeams, getUpcomingFixtures, getLiveFixtures } from "../services";
import { isToday } from "../utils/fixtureHelpers";
import { SITE } from "../config/site";

const FAQ = [
  {
    q: "What is FOOTY254?",
    a: "An AI football analysis app. It studies recent form, goals, shots, rest days and team strength to estimate who is most likely to win each fixture in the top leagues.",
  },
  {
    q: "How accurate are the predictions?",
    a: "Football is hard to call. Predictions are probabilities, not guarantees, and some matches are close to a coin toss. Use them as one input alongside your own judgement.",
  },
  {
    q: "What do I get with Premium?",
    a: "Win, draw and loss probabilities, expected goals, confidence scores and AI picks on every fixture, including live matches.",
  },
  {
    q: "How do I pay?",
    a: "Pay with M-Pesa (you get a prompt on your phone) or with a debit or credit card. Plans start from the Premium page.",
  },
  {
    q: "Is it safe to bet based on this?",
    a: "FOOTY254 gives analysis, not betting advice. You must be 18 or older to bet. Only stake what you can afford to lose.",
  },
];

function CountCard({ to, label, value, icon, hint }) {
  return (
    <Link
      to={to}
      className="group rounded-2xl border border-white/10 bg-pitch p-4 transition hover:border-signal/50 hover:bg-turf"
    >
      <div className="flex items-center justify-between text-chalk/70">
        {icon}
        <span className="text-xs opacity-0 transition group-hover:opacity-100">Open</span>
      </div>
      <p className="mt-3 text-3xl font-black tabular-nums">{value ?? "-"}</p>
      <p className="font-semibold">{label}</p>
      <p className="mt-0.5 text-xs text-chalk/60">{hint}</p>
    </Link>
  );
}

export default function Dashboard() {
  const { authenticated, user } = useAuth();
  const [counts, setCounts] = useState({ teams: null, upcoming: null, live: null, today: null });
  const [open, setOpen] = useState(0);

  useEffect(() => {
    let cancelled = false;

    Promise.allSettled([getTeams(), getUpcomingFixtures(), getLiveFixtures()]).then(
      ([teams, upcoming, live]) => {
        if (cancelled) return;
        const up = upcoming.status === "fulfilled" ? upcoming.value.fixtures : null;
        setCounts({
          teams: teams.status === "fulfilled" ? teams.value.teams.length : null,
          upcoming: up ? up.filter((m) => !isToday(m)).length : null,
          live: live.status === "fulfilled" ? live.value.count : null,
          today: up ? up.filter(isToday).length : null,
        });
      }
    );

    return () => {
      cancelled = true;
    };
  }, []);

  const hasContact = SITE.supportEmail || SITE.supportPhone || SITE.whatsapp;

  return (
    <div className="space-y-10">
      {/* Welcome */}
      <section className="overflow-hidden rounded-[30px] border border-white/10 bg-[linear-gradient(135deg,#1d4a2f,#0e2419_55%,#3a1519)] p-6 sm:p-10">
        <h1 className="font-display font-display-italic text-4xl leading-[1.05] sm:text-6xl">
          Smarter picks.
          <br />
          Better wins.
        </h1>
        <p className="mt-4 max-w-xl text-base leading-7 text-chalk/80">
          {authenticated ? `Welcome back, ${user?.first_name}. ` : "Welcome to FOOTY254. "}
          Our AI studies form, goals, shots and team strength across the world's top leagues and
          tells you who is most likely to win, with the numbers to back it up.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/predictions" className="rounded-xl bg-signal px-6 py-3 font-black text-ink">
            See predictions
          </Link>
          {authenticated ? (
            <Link to="/subscriptions" className="rounded-xl bg-white/10 px-6 py-3 font-bold">
              Go Premium
            </Link>
          ) : (
            <Link to="/register" className="rounded-xl bg-white/10 px-6 py-3 font-bold">
              Create a free account
            </Link>
          )}
        </div>
      </section>

      {/* Counts only; the fixtures themselves live on Predict */}
      <section aria-label="At a glance" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <CountCard to="/teams" label="Teams" value={counts.teams} icon={<Users size={20} />} hint="Browse every club" />
        <CountCard to="/predictions?view=upcoming" label="Upcoming" value={counts.upcoming} icon={<CalendarDays size={20} />} hint="Fixtures after today" />
        <CountCard to="/live" label="Live" value={counts.live} icon={<Radio size={20} />} hint="In play right now" />
        <CountCard to="/predictions?view=today" label="Today" value={counts.today} icon={<Clock3 size={20} />} hint="Kicking off today" />
      </section>

      {/* What it does */}
      <section>
        <h2 className="text-2xl font-black">What you get</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {[
            [Brain, "AI match picks", "Win, draw or loss probabilities for every fixture, built from recent form and team strength."],
            [Gauge, "Confidence and xG", "See how sure the model is and how many goals it expects from each side."],
            [Bell, "Live and alerts", "Follow matches in play with the AI's pick beside the score, and get alerts for your saved games."],
          ].map(([Icon, title, text]) => (
            <div key={title} className="rounded-2xl border border-white/10 bg-pitch p-5">
              <Icon className="text-signal" size={22} />
              <h3 className="mt-3 font-black">{title}</h3>
              <p className="mt-1 text-sm leading-6 text-chalk/70">{text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" aria-labelledby="faq-title">
        <h2 id="faq-title" className="text-2xl font-black">
          Frequently asked questions
        </h2>
        <div className="mt-4 divide-y divide-white/10 rounded-2xl border border-white/10 bg-pitch">
          {FAQ.map((item, i) => (
            <div key={item.q}>
              <button
                type="button"
                aria-expanded={open === i}
                onClick={() => setOpen(open === i ? -1 : i)}
                className="flex w-full items-center justify-between gap-4 p-4 text-left font-bold"
              >
                {item.q}
                <ChevronDown size={18} className={`shrink-0 transition ${open === i ? "rotate-180" : ""}`} />
              </button>
              {open === i && <p className="px-4 pb-4 text-sm leading-6 text-chalk/75">{item.a}</p>}
            </div>
          ))}
        </div>
      </section>

      {/* Support */}
      <section id="support" aria-labelledby="support-title" className="rounded-2xl border border-white/10 bg-pitch p-6">
        <h2 id="support-title" className="text-2xl font-black">
          Support and contact
        </h2>
        {hasContact ? (
          <>
            <p className="mt-2 text-chalk/75">
              Payment problem, account question or feedback? We reply {SITE.supportHours}.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              {SITE.supportEmail && (
                <a href={`mailto:${SITE.supportEmail}`} className="rounded-xl bg-turf px-5 py-3 font-semibold">
                  {SITE.supportEmail}
                </a>
              )}
              {SITE.supportPhone && (
                <a href={`tel:${SITE.supportPhone}`} className="rounded-xl bg-turf px-5 py-3 font-semibold">
                  {SITE.supportPhone}
                </a>
              )}
              {SITE.whatsapp && (
                <a
                  href={`https://wa.me/${SITE.whatsapp}`}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-xl bg-turf px-5 py-3 font-semibold"
                >
                  WhatsApp us
                </a>
              )}
            </div>
          </>
        ) : (
          <p className="mt-2 text-chalk/75">
            Have a question? Check the answers above first. Signed-in members can manage their
            account and devices under Settings and Security.
          </p>
        )}
      </section>
    </div>
  );
}

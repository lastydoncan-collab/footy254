import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  Bell,
  CreditCard,
  Heart,
  Home,
  Menu,
  Radio,
  Settings,
  Shield,
  Sparkles,
  LogOut,
  User,
  LogIn,
  UserPlus,
  X,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";

const navItems = [
  { name: "Home", path: "/", icon: Home, primary: true },
  { name: "Live", path: "/live", icon: Radio, primary: true },
  { name: "Predict", path: "/predictions", icon: Sparkles, primary: true },
  { name: "Saved", path: "/favorites", icon: Heart, primary: true },
  { name: "Premium", path: "/subscriptions", icon: CreditCard },
  { name: "Alerts", path: "/notifications", icon: Bell },
  { name: "Analytics", path: "/analytics", icon: BarChart3 },
  { name: "Security", path: "/security", icon: Shield },
  { name: "Settings", path: "/settings", icon: Settings },
];

function NavItem({ item, compact = false }) {
  const Icon = item.icon;

  return (
    <NavLink
      to={item.path}
      end={item.path === "/"}
      className={({ isActive }) => `
        group
        flex
        items-center
        justify-center
        gap-2
        rounded-2xl
        px-3
        py-2.5
        text-xs
        font-semibold
        transition-all
        duration-200

        ${
          isActive
            ? "bg-signal text-ink shadow-[0_10px_30px_rgba(31,230,173,.30)] scale-[1.02]"
            : "text-slate-300 hover:bg-white/10 hover:text-white"
        }

        ${compact ? "flex-col gap-1 px-2 py-2" : "justify-start"}
      `}
    >
      <Icon size={compact ? 20 : 18} />
      <span>{item.name}</span>
    </NavLink>
  );
}

export default function Sidebar() {
  const { authenticated, user, logout } = useAuth();
  const location = useLocation();

  // navItems never changes across renders, so deriving these on every
  // render (including on every keystroke elsewhere in the app, since
  // Sidebar stays mounted across route changes) is wasted work for no
  // visual benefit — memoize them once.
  const primaryItems = useMemo(
    () => navItems.filter((item) => item.primary),
    []
  );

  const secondaryItems = useMemo(
    () => navItems.filter((item) => !item.primary),
    []
  );

  // The bottom nav only has room for 5 slots on mobile: the 4 primary
  // destinations plus a "More" button. Everything else (Alerts, Analytics,
  // Security, Settings, plus account actions) lives behind that button —
  // previously it didn't exist anywhere on mobile, silently locking small
  // screens out of Security, Settings, and even Logout entirely.
  const [moreOpen, setMoreOpen] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);

  // Close the sheet on navigation. Doing this as a synchronous state
  // adjustment during render (React's documented pattern for "reset state
  // when a prop changes") rather than inside a useEffect avoids an extra
  // render pass + effect-triggered cascading render on every navigation.
  const [lastPathname, setLastPathname] = useState(location.pathname);

  if (location.pathname !== lastPathname) {
    setLastPathname(location.pathname);
    if (moreOpen) {
      setMoreOpen(false);
    }
  }

  const moreButtonRef = useRef(null);
  const sheetCloseRef = useRef(null);
  const hasOpenedSheetRef = useRef(false);

  const isOnSecondaryPage = secondaryItems.some(
    (item) => item.path === location.pathname
  );

  // Let Escape close the sheet too, since it renders as a modal-style
  // overlay.
  useEffect(() => {
    if (!moreOpen) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setMoreOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [moreOpen]);

  // Basic focus management for the sheet: move focus into it on open (so
  // keyboard/screen-reader users land somewhere sensible instead of the
  // background), and return focus to the trigger button on close so
  // keyboard focus doesn't silently vanish into the page body.
  useEffect(() => {
    if (moreOpen) {
      hasOpenedSheetRef.current = true;
      sheetCloseRef.current?.focus();
    } else if (hasOpenedSheetRef.current) {
      moreButtonRef.current?.focus();
    }
  }, [moreOpen]);

  return (
    <>
      {/* =========================================================
          DESKTOP SIDEBAR
          ========================================================= */}

      <aside
        className="
          fixed
          left-4
          top-4
          z-40
          hidden
          h-[calc(100vh-2rem)]
          w-24
          overflow-hidden
          rounded-[28px]
          border
          border-white/10
          bg-pitch/95
          shadow-2xl
          backdrop-blur
          lg:flex
          lg:flex-col
        "
      >
        {/* =======================================================
            FOOTY254 COMPACT BRAND
            ======================================================= */}

        <div
          className="
            shrink-0
            border-b
            border-white/10
            bg-pitch/95
            p-3
          "
        >
          <Link
            to="/"
            aria-label="FOOTY254 Home"
            className="
              group
              flex
              h-12
              w-full
              items-center
              justify-center
              rounded-2xl
              transition-all
              duration-200
              hover:bg-white/5
            "
          >
            {logoFailed ? (
              // Fallback if the asset ever fails to load (bad deploy, wrong
              // path, offline PWA cache miss) — keeps the brand mark and
              // the link functional instead of showing a broken-image icon.
              <div
                className="
                  flex
                  h-11
                  w-11
                  items-center
                  justify-center
                  rounded-full
                  bg-signal
                  text-xs
                  font-black
                  text-ink
                "
              >
                F254
              </div>
            ) : (
              <span
                className="
                  relative
                  flex
                  h-11
                  w-11
                  shrink-0
                  items-center
                  justify-center
                  overflow-hidden
                  rounded-full
                  ring-2
                  ring-signal/40
                  transition-all
                  duration-200
                  group-hover:scale-[1.06]
                  group-hover:ring-signal/70
                "
              >
                <img
                  src="/footy254-icon.png"
                  alt="FOOTY254"
                  width="44"
                  height="44"
                  onError={() => setLogoFailed(true)}
                  className="
                    h-full
                    w-full
                    object-cover
                    drop-shadow-[0_0_10px_rgba(31,230,173,.20)]
                  "
                />
              </span>
            )}
          </Link>
        </div>

        {/* =======================================================
            SCROLLABLE NAVIGATION
            ======================================================= */}

        <div
          className="
            min-h-0
            flex-1
            overflow-y-auto
            overflow-x-hidden
            px-3
            py-3
          "
        >
          <nav className="flex flex-col gap-2">
            {primaryItems.map((item) => (
              <NavItem
                key={item.name}
                item={item}
                compact
              />
            ))}

            {/* Visual separation between core navigation and account/tools,
                so the sidebar reads as two groups instead of one flat list. */}
            <div className="my-1 border-t border-white/10" />

            {secondaryItems.map((item) => (
              <NavItem
                key={item.name}
                item={item}
                compact
              />
            ))}
          </nav>
        </div>

        {/* =======================================================
            BOTTOM USER PANEL
            ======================================================= */}

        <div
          className="
            shrink-0
            border-t
            border-white/10
            bg-pitch/95
            p-3
          "
        >
          {authenticated ? (
            <>
              <div className="mb-3 flex flex-col items-center">
                <div
                  className="
                    flex
                    h-11
                    w-11
                    items-center
                    justify-center
                    rounded-full
                    bg-signal
                    text-ink
                  "
                >
                  <User size={18} />
                </div>

                <p
                  className="
                    mt-2
                    max-w-full
                    truncate
                    text-center
                    text-[11px]
                    font-bold
                    text-white
                  "
                  title={user?.username || ""}
                >
                  {user?.username}
                </p>

                <p className="text-[10px] text-slate-400">
                  {user?.role}
                </p>
              </div>

              <button
                type="button"
                onClick={logout}
                className="
                  flex
                  w-full
                  flex-col
                  items-center
                  gap-1
                  rounded-2xl
                  px-2
                  py-2
                  text-xs
                  font-semibold
                  text-slate-300
                  transition
                  hover:bg-red-500/20
                  hover:text-red-300
                "
              >
                <LogOut size={18} />
                <span>Logout</span>
              </button>
            </>
          ) : (
            <div className="space-y-2">
              <Link
                to="/login"
                className="
                  flex
                  flex-col
                  items-center
                  rounded-2xl
                  px-2
                  py-2
                  text-xs
                  font-semibold
                  text-slate-300
                  transition
                  hover:bg-white/10
                  hover:text-white
                "
              >
                <LogIn size={18} />
                <span>Login</span>
              </Link>

              <Link
                to="/register"
                className="
                  flex
                  flex-col
                  items-center
                  rounded-2xl
                  bg-signal
                  px-2
                  py-2
                  text-xs
                  font-bold
                  text-ink
                  transition
                  hover:opacity-90
                "
              >
                <UserPlus size={18} />
                <span>Register</span>
              </Link>
            </div>
          )}
        </div>
      </aside>

      {/* =========================================================
          MOBILE NAVIGATION (4 primary destinations + More)
          ========================================================= */}

      <nav
        className="
          fixed
          inset-x-3
          bottom-3
          z-50
          grid
          grid-cols-5
          gap-1
          rounded-[26px]
          border
          border-white/10
          bg-pitch/95
          p-2
          shadow-2xl
          backdrop-blur
          lg:hidden
        "
      >
        {primaryItems.map((item) => (
          <NavItem
            key={item.name}
            item={item}
            compact
          />
        ))}

        <button
          type="button"
          ref={moreButtonRef}
          onClick={() => setMoreOpen(true)}
          aria-label="More menu"
          aria-expanded={moreOpen}
          className={`
            group
            flex
            flex-col
            items-center
            justify-center
            gap-1
            rounded-2xl
            px-2
            py-2
            text-xs
            font-semibold
            transition-all
            duration-200

            ${
              isOnSecondaryPage
                ? "bg-signal text-ink shadow-[0_10px_30px_rgba(31,230,173,.30)]"
                : "text-slate-300 hover:bg-white/10 hover:text-white"
            }
          `}
        >
          <Menu size={20} />
          <span>More</span>
        </button>
      </nav>

      {/* =========================================================
          MOBILE "MORE" SHEET
          Alerts, Analytics, Security, Settings, account actions --
          previously reachable only on desktop.
          ========================================================= */}

      {moreOpen && (
        <div className="fixed inset-0 z-[60] lg:hidden">
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setMoreOpen(false)}
            className="absolute inset-0 h-full w-full bg-black/60 backdrop-blur-sm"
          />

          <div
            className="
              absolute
              inset-x-3
              bottom-3
              rounded-[26px]
              border
              border-white/10
              bg-pitch
              p-4
              shadow-2xl
            "
          >
            <div className="mb-3 flex items-center justify-between px-1">
              <span className="text-sm font-black text-white">Menu</span>

              <button
                type="button"
                ref={sheetCloseRef}
                onClick={() => setMoreOpen(false)}
                aria-label="Close menu"
                className="rounded-full p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <div className="grid grid-cols-4 gap-2">
              {secondaryItems.map((item) => (
                <NavItem
                  key={item.name}
                  item={item}
                  compact
                />
              ))}
            </div>

            <div className="mt-4 border-t border-white/10 pt-4">
              {authenticated ? (
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-signal text-ink">
                      <User size={18} />
                    </div>

                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-white">
                        {user?.username}
                      </p>
                      <p className="text-xs text-slate-400">{user?.role}</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={logout}
                    className="flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold text-slate-300 transition hover:bg-red-500/20 hover:text-red-300"
                  >
                    <LogOut size={16} />
                    Logout
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <Link
                    to="/login"
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-300 transition hover:bg-white/10 hover:text-white"
                  >
                    <LogIn size={16} />
                    Login
                  </Link>

                  <Link
                    to="/register"
                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-signal px-3 py-2.5 text-sm font-bold text-ink transition hover:opacity-90"
                  >
                    <UserPlus size={16} />
                    Register
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

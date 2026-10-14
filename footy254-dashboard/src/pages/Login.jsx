import { useState } from "react";
import {
  Link,
  useLocation,
  useNavigate,
} from "react-router-dom";

import {
  Eye,
  EyeOff,
} from "lucide-react";

import { useAuth } from "../context/AuthContext";

export default function Login() {

  const navigate = useNavigate();

  const location = useLocation();

  const { login, completeTwoFactor } = useAuth();

  const [challenge, setChallenge] = useState("");

  const [code, setCode] = useState("");

  const from =
    (location.state?.from?.pathname || "/") +
    (location.state?.from?.search || "");

  const [form, setForm] = useState({

    email: "",

    password: "",

  });

  const [showPassword, setShowPassword] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const [message] = useState(
    location.state?.registrationSuccess
      ? "Account created. Sign in to continue."
      : location.state?.passwordResetSuccess
      ? "Password updated. Sign in with your new password."
      : ""
  );

  // =====================================
  // INPUT CHANGE
  // =====================================

  function handleChange(event) {

    const { name, value } = event.target;

    setForm(previous => ({

      ...previous,

      [name]: value,

    }));

  }

  // =====================================
  // LOGIN
  // =====================================

  async function handleSubmit(event) {

    event.preventDefault();

    setError("");

    setLoading(true);

    try {

      if (challenge) {

        await completeTwoFactor(challenge, code.trim());

      } else {

        const response = await login(

          form.email.trim(),

          form.password

        );

        if (response.two_factor_required) {

          setChallenge(response.challenge);

          setLoading(false);

          return;

        }

      }

      navigate(

        from,

        {

          replace: true,

        }

      );

    } catch (err) {

      setError(

          err?.detail ||

          err?.message ||

          "Unable to login."

      );

    } finally {

      setLoading(false);

    }

  }

  return (

    <div className="flex min-h-screen items-center justify-center bg-ink px-6">

      <div className="w-full max-w-md rounded-3xl border border-white/10 bg-pitch p-8 shadow-2xl">

        <div className="flex justify-center">
          <img
            src="/footy254-icon.png"
            alt="FOOTY254"
            width="64"
            height="64"
            className="h-16 w-16 rounded-full object-cover ring-2 ring-signal/40 drop-shadow-[0_0_16px_rgba(31,230,173,.25)]"
          />
        </div>

        <h1 className="mt-6 text-3xl font-black text-white">

          Welcome Back

        </h1>

        <p className="mt-2 text-slate-400">

          Sign in to continue using FOOTY254

        </p>

        {error && (

          <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/20 p-3 text-red-300">

            {error}

          </div>

        )}

        {message && (

          <div className="mt-5 rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-green-300">

            {message}

          </div>

        )}

        <form

          onSubmit={handleSubmit}

          className="mt-6 space-y-5"

        >

          {!challenge && (<>


          <div>

            <label className="text-sm font-semibold text-slate-300">

              Email

            </label>

            <input

              type="email"

              name="email"

              autoComplete="email"

              required

                value={form.email}

              onChange={handleChange}

              placeholder="Enter your email"

              className="mt-2 w-full rounded-xl border border-white/10 bg-turf px-4 py-3 text-white outline-none transition focus:border-signal"

            />

          </div>

          <div>

            <div className="flex items-center justify-between">

              <label className="text-sm font-semibold text-slate-300">

                Password

              </label>

              <Link
                to="/forgot-password"
                className="text-sm font-semibold text-signal hover:underline"
              >
                Forgot password?
              </Link>

            </div>

            <div className="relative mt-2">

              <input

                type={

                  showPassword

                    ? "text"

                    : "password"

                }

                name="password"

                autoComplete="current-password"

                required

                value={form.password}

                onChange={handleChange}

                placeholder="Enter your password"

                className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 pr-14 text-white outline-none transition focus:border-signal"

              />

              <button

                type="button"

                onClick={() =>

                  setShowPassword(

                    previous => !previous

                  )

                }

                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-white"

              >

                {

                  showPassword

                    ? <EyeOff size={20}/>

                    : <Eye size={20}/>

                }

              </button>

            </div>

          </div>

          </>)}

          {challenge && (

            <div>

              <label className="text-sm font-semibold text-slate-300" htmlFor="otp">

                Authentication code

              </label>

              <input

                id="otp"

                inputMode="numeric"

                autoComplete="one-time-code"

                autoFocus

                required

                value={code}

                onChange={(e) => setCode(e.target.value)}

                placeholder="6-digit code or recovery code"

                className="mt-2 w-full rounded-xl px-4 py-3 text-center text-lg tracking-widest outline-none"

              />

              <p className="mt-2 text-xs text-slate-400">

                Open your authenticator app and enter the current code for FOOTY254.

              </p>

              <button

                type="button"

                onClick={() => { setChallenge(""); setCode(""); setError(""); }}

                className="mt-2 text-xs font-semibold text-signal hover:underline"

              >

                Use a different account

              </button>

            </div>

          )}

          <button

            type="submit"

            disabled={loading}

            className="w-full rounded-xl bg-signal py-3 font-black text-ink transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"

          >

            {

              loading

                ? "Signing In..."

                : challenge ? "Verify and sign in" : "Login"

            }

          </button>

        </form>

        <p className="mt-6 text-center text-sm text-slate-400">

          Don't have an account?

          <Link

            to="/register"

            className="ml-2 font-bold text-signal hover:underline"

          >

            Register

          </Link>

        </p>

      </div>

    </div>

  );

}

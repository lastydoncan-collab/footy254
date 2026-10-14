import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";

import { useAuth } from "../context/AuthContext";

export default function Register() {

  const navigate = useNavigate();

  const { register } = useAuth();

  const [form, setForm] = useState({

    first_name: "",

    last_name: "",

    username: "",

    email: "",

    password: "",

  });

  const [showPassword, setShowPassword] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  // ======================================
  // INPUT
  // ======================================

  function handleChange(event) {

    const { name, value } = event.target;

    setForm(previous => ({

      ...previous,

      [name]: value,

    }));

  }

  // ======================================
  // REGISTER
  // ======================================

  async function handleSubmit(event) {

    event.preventDefault();

    setError("");

    setLoading(true);

    try {

      await register({

        first_name: form.first_name.trim(),

        last_name: form.last_name.trim(),

        username: form.username.trim(),

        email: form.email.trim(),

        password: form.password,

      });

      navigate("/login", {
        state: {
          registrationSuccess: true,
          email: form.email.trim(),
        },
        replace: true,

      });

    }

    catch (err) {

      setError(

        err.message ||

        "Registration failed."

      );

    }

    finally {

      setLoading(false);

    }

  }

  return (

    <div className="flex min-h-screen items-center justify-center bg-ink px-6">

      <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-pitch p-8 shadow-2xl">

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

          Create Account

        </h1>

        <p className="mt-2 text-slate-400">

          Join FOOTY254 AI Predictions

        </p>

        {

          error && (

            <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/20 p-3 text-red-300">

              {error}

            </div>

          )

        }

        <form

          onSubmit={handleSubmit}

          className="mt-6 space-y-4"

        >

          <input

            name="first_name"

            required

            autoComplete="given-name"

            placeholder="First Name"

            value={form.first_name}

            onChange={handleChange}

            className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 text-white outline-none focus:border-signal"

          />

          <input

            name="last_name"

            required

            autoComplete="family-name"

            placeholder="Last Name"

            value={form.last_name}

            onChange={handleChange}

            className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 text-white outline-none focus:border-signal"

          />

          <input

            name="username"

            required

            minLength={3}

            maxLength={30}

            pattern="[A-Za-z0-9_.\-]{3,30}"

            title="3-30 characters: letters, numbers, dots, underscores or hyphens"

            autoComplete="username"

            placeholder="Username"

            value={form.username}

            onChange={handleChange}

            className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 text-white outline-none focus:border-signal"

          />

          <input

            type="email"

            name="email"

            required

            autoComplete="email"

            placeholder="Email"

            value={form.email}

            onChange={handleChange}

            className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 text-white outline-none focus:border-signal"

          />

          <div className="relative">

            <input

              type={

                showPassword

                  ? "text"

                  : "password"

              }

              name="password"

              required

              minLength={8}

              maxLength={72}

              autoComplete="new-password"

              placeholder="Password"

              value={form.password}

              onChange={handleChange}

              className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 pr-14 text-white outline-none focus:border-signal"

            />

            <button

              type="button"

              onClick={() =>

                setShowPassword(

                  previous => !previous

                )

              }

              className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"

            >

              {

                showPassword

                  ? <EyeOff size={20}/>

                  : <Eye size={20}/>

              }

            </button>

          </div>

          <button

            type="submit"

            disabled={loading}

            className="w-full rounded-xl bg-signal py-3 font-black text-ink transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"

          >

            {

              loading

                ? "Creating Account..."

                : "Create Account"

            }

          </button>

        </form>

        <p className="mt-6 text-center text-slate-400">

          Already have an account?

          <Link

            to="/login"

            className="ml-2 font-bold text-signal hover:underline"

          >

            Login

          </Link>

        </p>

      </div>

    </div>

  );

}

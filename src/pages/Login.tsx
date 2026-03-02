import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { LogIn } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-industrial-900">
      <div className="w-full max-w-md space-y-8 rounded-2xl bg-white p-8 shadow-xl">
        {/* Logo */}
        <div className="text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-industrial-600 text-white font-heading text-xl font-bold">
            M
          </div>
          <h2 className="mt-4 text-2xl font-bold text-slate-900 font-heading">
            Welcome back
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Sign in to your MRO sourcing platform
          </p>
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-slate-700"
            >
              Email address
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:border-industrial-500 focus:outline-none focus:ring-2 focus:ring-industrial-500/20"
              placeholder="you@company.com"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-slate-700"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:border-industrial-500 focus:outline-none focus:ring-2 focus:ring-industrial-500/20"
              placeholder="Enter your password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-industrial-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-industrial-700 focus:outline-none focus:ring-2 focus:ring-industrial-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            ) : (
              <>
                <LogIn className="h-4 w-4" />
                Sign in
              </>
            )}
          </button>
        </form>

        {/* Demo credentials */}
        <div className="rounded-lg bg-industrial-50 border border-industrial-200 px-4 py-3">
          <p className="text-xs font-semibold text-industrial-800 mb-1">Demo Credentials</p>
          <div className="flex items-center justify-between text-sm text-industrial-700">
            <span>demo@indusai.com</span>
            <span className="font-mono">demo1234</span>
          </div>
          <button
            type="button"
            onClick={() => {
              setEmail("demo@indusai.com");
              setPassword("demo1234");
            }}
            className="mt-2 w-full rounded-md bg-industrial-100 px-3 py-1.5 text-xs font-medium text-industrial-700 hover:bg-industrial-200 transition-colors"
          >
            Fill demo credentials
          </button>
        </div>

        <p className="text-center text-sm text-slate-500">
          Don't have an account?{" "}
          <Link
            to="/signup"
            className="font-medium text-industrial-600 hover:text-industrial-700"
          >
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}

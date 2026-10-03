import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { getToken, api } from "../api/client";

const schema = z.object({
  email: z.string().trim().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
type Values = z.infer<typeof schema>;

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate();
  const location = useLocation();
  const isLogin = mode === "login";
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });
  const mutation = useMutation({
    mutationFn: async ({ email, password }: Values) => {
      if (isLogin) await api.login(email, password);
      else await api.signup(email, password);
    },
    onSuccess: () => navigate(isLogin ? from : "/login", { replace: true }),
  });

  if (getToken() && isLogin) return <Navigate to="/" replace />;

  return (
    <main className="auth-shell">
      <section className="auth-card panel">
        <Link className="brand auth-brand" to="/">
          <span className="brand-mark">J</span> JobTrack
        </Link>
        <p className="eyebrow">{isLogin ? "WELCOME BACK" : "A FRESH START"}</p>
        <h1>{isLogin ? "Sign in to your tracker" : "Create your account"}</h1>
        <p className="muted">
          {isLogin
            ? "Pick up where your job search left off."
            : "Keep every application and follow-up in one place."}
        </p>
        <form
          className="form-stack"
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
        >
          <label>
            Email address
            <input autoComplete="email" type="email" {...register("email")} />
            {errors.email && <small className="field-error">{errors.email.message}</small>}
          </label>
          <label>
            Password
            <input
              autoComplete={isLogin ? "current-password" : "new-password"}
              type="password"
              {...register("password")}
            />
            {errors.password && (
              <small className="field-error">{errors.password.message}</small>
            )}
          </label>
          {mutation.error && (
            <div className="error-panel" role="alert">
              {mutation.error.message}
            </div>
          )}
          <button className="button button-full" disabled={mutation.isPending} type="submit">
            {mutation.isPending ? "One moment…" : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>
        <p className="auth-switch">
          {isLogin ? "New to JobTrack?" : "Already have an account?"}{" "}
          <Link to={isLogin ? "/signup" : "/login"}>
            {isLogin ? "Create an account" : "Sign in"}
          </Link>
        </p>
        {!isLogin && <p className="auth-switch">Public demo: please use sample data only. Don’t upload a real resume.</p>}
      </section>
    </main>
  );
}

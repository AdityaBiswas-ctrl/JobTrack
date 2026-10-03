import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ToastProvider } from "./components/Toast";

const ApplicationDetail = lazy(() => import("./pages/ApplicationDetail").then((module) => ({ default: module.ApplicationDetail })));
const Applications = lazy(() => import("./pages/Applications").then((module) => ({ default: module.Applications })));
const AuthPage = lazy(() => import("./pages/AuthPage").then((module) => ({ default: module.AuthPage })));
const Dashboard = lazy(() => import("./pages/Dashboard").then((module) => ({ default: module.Dashboard })));
const Resumes = lazy(() => import("./pages/Resumes").then((module) => ({ default: module.Resumes })));
const Settings = lazy(() => import("./pages/Settings").then((module) => ({ default: module.Settings })));

export function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <SessionRedirect />
        <Suspense fallback={<main className="page-wrap"><p role="status">Loading page…</p></main>}>
          <Routes>
            <Route element={<AuthPage mode="login" />} path="/login" />
            <Route element={<AuthPage mode="signup" />} path="/signup" />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route element={<Dashboard />} path="/" />
                <Route element={<Applications />} path="/applications" />
                <Route element={<ApplicationDetail />} path="/applications/:id" />
                <Route element={<Resumes />} path="/resumes" />
                <Route element={<Settings />} path="/settings" />
              </Route>
            </Route>
            <Route path="*" element={<Navigate replace to="/" />} />
          </Routes>
        </Suspense>
      </ToastProvider>
    </ErrorBoundary>
  );
}

export function SessionRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    const onUnauthorized = () => navigate("/login", { replace: true });
    window.addEventListener("jobtrack:unauthorized", onUnauthorized);
    return () => window.removeEventListener("jobtrack:unauthorized", onUnauthorized);
  }, [navigate]);
  return null;
}

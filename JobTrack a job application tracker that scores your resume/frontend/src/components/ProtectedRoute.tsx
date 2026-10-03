import { Navigate, Outlet, useLocation } from "react-router-dom";
import { getToken } from "../api/client";

export function ProtectedRoute() {
  const location = useLocation();
  return getToken() ? <Outlet /> : <Navigate to="/login" replace state={{ from: location }} />;
}

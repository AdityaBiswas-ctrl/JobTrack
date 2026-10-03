import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { setToken } from "../api/client";

export function Layout() {
  const navigate = useNavigate();
  function logout() {
    setToken(null);
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand" to="/">
          <span className="brand-mark">J</span> JobTrack
        </NavLink>
        <nav aria-label="Main navigation" className="nav-links">
          <NavLink to="/">Dashboard</NavLink>
          <NavLink to="/applications">Applications</NavLink>
          <NavLink to="/resumes">Resumes</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
        <button className="button button-quiet button-small" onClick={logout} type="button">
          Log out
        </button>
      </header>
      <main className="page-wrap">
        <Outlet />
      </main>
      <footer className="footer">A calmer way to keep your next move in sight.</footer>
    </div>
  );
}

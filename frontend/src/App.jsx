import { Navigate, Route, Routes } from "react-router-dom";
import { ROLE_HOME, useAuth } from "./auth/AuthContext.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Login from "./pages/Login.jsx";

// Client-side guard is for UX only. The backend enforces every permission.
function RequireRole({ role, children }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-6 text-slate-500">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {Object.entries(ROLE_HOME).map(([role, path]) => (
        <Route
          key={role}
          path={path}
          element={
            <RequireRole role={role}>
              <Dashboard role={role} />
            </RequireRole>
          }
        />
      ))}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

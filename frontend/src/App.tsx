import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import ClaimDetail from "./pages/ClaimDetail";
import ClaimsList from "./pages/ClaimsList";
import Login from "./pages/Login";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <p>Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function Shell() {
  const { user, logout } = useAuth();
  return (
    <div className="app-shell">
      {user && (
        <div className="topbar">
          <strong>Claims Document Processor</strong>
          <div>
            <span className="muted" style={{ marginRight: "1rem" }}>
              {user.email} ({user.role})
            </span>
            <button className="secondary" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      )}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/claims"
          element={
            <RequireAuth>
              <ClaimsList />
            </RequireAuth>
          }
        />
        <Route
          path="/claims/:id"
          element={
            <RequireAuth>
              <ClaimDetail />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/claims" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}

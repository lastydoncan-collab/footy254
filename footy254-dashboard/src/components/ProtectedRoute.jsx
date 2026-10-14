import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, requireAdmin = false }) {
  const { authenticated, isAdmin, loading } = useAuth();
  const location = useLocation();

  // Wait until authentication state has loaded
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink text-white">
        <div className="text-center">
          <h2 className="text-xl font-black">FOOTY254</h2>
          <p className="mt-2 text-slate-400">
            Loading...
          </p>
        </div>
      </div>
    );
  }

  // User is not logged in
  if (!authenticated) {
    // Remember the destination so Login can send the user back to it.
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/" replace />;
  }

  // User is authenticated
  return children;
}
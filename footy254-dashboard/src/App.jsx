import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

import DashboardLayout from "./layouts/DashboardLayout";
import ProtectedRoute from "./components/ProtectedRoute";

// Public pages
import Dashboard from "./pages/Dashboard";
import Predictions from "./pages/Predictions";
import PredictionDetails from "./pages/PredictionDetails";
import LiveMatches from "./pages/LiveMatches";
import Teams from "./pages/Teams";
import CardReturn from "./pages/CardReturn";
import Analytics from "./pages/Analytics";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Subscriptions from "./pages/Subscriptions";
import SubscriptionCheckout from "./pages/SubscriptionCheckout";

// Protected pages
import Favorites from "./pages/Favorites";
import Notifications from "./pages/Notifications";
import Settings from "./pages/Settings";
import Security from "./pages/Security";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        {/* Pages that use the common dashboard layout */}
        <Route element={<DashboardLayout />}>

          {/* Public */}
          <Route path="/" element={<Dashboard />} />
          <Route path="/predictions" element={<Predictions />} />
          <Route path="/predictions/:matchId" element={<PredictionDetails />} />
          <Route path="/live" element={<LiveMatches />} />
          <Route path="/teams" element={<Teams />} />
          <Route
            path="/subscription/card-return"
            element={
              <ProtectedRoute>
                <CardReturn />
              </ProtectedRoute>
            }
          />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/subscriptions" element={<Subscriptions />} />
          <Route
                path="/subscription/checkout/:planId"
                element={<SubscriptionCheckout />}
            />

          {/* Protected */}
          <Route
            path="/favorites"
            element={
              <ProtectedRoute>
                <Favorites />
              </ProtectedRoute>
            }
          />

          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <Notifications />
              </ProtectedRoute>
            }
          />

          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />

          <Route
            path="/security"
            element={
              <ProtectedRoute>
                <Security />
              </ProtectedRoute>
            }
          />

        </Route>

        {/* Authentication pages (outside dashboard layout) */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />

        <Route
            path="*"
            element={<Navigate to="/" replace />}
        />

      </Routes>
    </BrowserRouter>
  );
}

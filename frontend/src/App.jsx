import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import BottomNav from "./components/BottomNav.jsx";
import InstallPrompt from "./components/InstallPrompt.jsx";
import OfflineBanner from "./components/OfflineBanner.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import { useAuth } from "./context/AuthContext.jsx";
import { TourAutoStartGate, TourProvider, TourReplayButton } from "./tour/Tour.jsx";
import Calendar from "./pages/Calendar.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import DocumentEditor from "./pages/DocumentEditor.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import History from "./pages/History.jsx";
import JobDetail from "./pages/JobDetail.jsx";
import Jobs from "./pages/Jobs.jsx";
import Login from "./pages/Login.jsx";
import Profile from "./pages/Profile.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import SavedJobs from "./pages/SavedJobs.jsx";
import Signup from "./pages/Signup.jsx";

function RequireAuth({ children }) {
  const { user, booting } = useAuth();
  const location = useLocation();

  if (booting) return <div className="boot">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

const PROTECTED = [
  ["/", Dashboard],
  ["/jobs", Jobs],
  ["/jobs/:jobId", JobDetail],
  ["/calendar", Calendar],
  ["/saved", SavedJobs],
  ["/history", History],
  ["/documents/:documentId", DocumentEditor],
  ["/profile", Profile],
];

export default function App() {
  const { user } = useAuth();
  const { pathname } = useLocation();

  return (
    <div className="app">
      <TourProvider>
        <OfflineBanner />
        <ThemeToggle />
        <Routes>
          <Route
            path="/login"
            element={user ? <Navigate to="/" replace /> : <Login />}
          />
          <Route
            path="/signup"
            element={user ? <Navigate to="/" replace /> : <Signup />}
          />
          <Route
            path="/forgot-password"
            element={user ? <Navigate to="/" replace /> : <ForgotPassword />}
          />
          {/* Reachable signed in or out, so a reset link is never swallowed by a redirect. */}
          <Route path="/reset-password" element={<ResetPassword />} />

          {PROTECTED.map(([path, Page]) => (
            <Route
              key={path}
              path={path}
              element={
                <RequireAuth>
                  <Page />
                </RequireAuth>
              }
            />
          ))}

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        {user && <InstallPrompt />}
        {user && <BottomNav />}
        {/* The tour runs on the home page, so its replay button lives only there
            instead of floating over content on every other page. */}
        {user && pathname === "/" && <TourReplayButton />}
        <TourAutoStartGate />
      </TourProvider>
    </div>
  );
}

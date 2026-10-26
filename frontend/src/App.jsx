import { Navigate, Route, Routes } from "react-router-dom";
import { ROLE_HOME, useAuth } from "./auth/AuthContext.jsx";
import AdminHome from "./pages/admin/AdminHome.jsx";
import ApplicantHome from "./pages/applicant/ApplicantHome.jsx";
import ApplicationWorkspace from "./pages/applicant/ApplicationWorkspace.jsx";
import Login from "./pages/Login.jsx";
import CaseReview from "./pages/officer/CaseReview.jsx";
import Queue from "./pages/officer/Queue.jsx";
import { InspectorCase, InspectorHome } from "./pages/inspector/InspectorPages.jsx";
import ReportPage from "./pages/ReportPage.jsx";
import RuleEditor from "./pages/RuleEditor.jsx";
import RuleViewer from "./pages/RuleViewer.jsx";

// Client-side guard is for UX only. The backend enforces every permission.
function RequireRole({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-6 text-slate-500">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return children;
}

function guarded(roles, element) {
  return <RequireRole roles={roles}>{element}</RequireRole>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route path="/applicant" element={guarded(["applicant"], <ApplicantHome />)} />
      <Route path="/applicant/applications/:id" element={guarded(["applicant"], <ApplicationWorkspace />)} />

      <Route path="/officer" element={guarded(["scrutiny_officer"], <Queue title="Scrutiny queue" basePath="/officer" />)} />
      <Route path="/officer/applications/:id" element={guarded(["scrutiny_officer"], <CaseReview basePath="/officer" />)} />

      <Route path="/senior" element={guarded(["senior_authority"], <Queue title="Overview" basePath="/senior" defaultFilter="escalated" senior />)} />
      <Route path="/senior/applications/:id" element={guarded(["senior_authority"], <CaseReview basePath="/senior" />)} />

      <Route path="/inspector" element={guarded(["inspector"], <InspectorHome />)} />
      <Route path="/inspector/applications/:id" element={guarded(["inspector"], <InspectorCase />)} />
      <Route path="/admin" element={guarded(["admin"], <AdminHome />)} />
      <Route path="/admin/rules" element={guarded(["admin"], <RuleEditor />)} />
      <Route path="/senior/rules" element={guarded(["senior_authority"], <RuleEditor />)} />
      <Route path="/officer/rules" element={guarded(["scrutiny_officer"], <RuleViewer />)} />

      <Route path="/applications/:id/report" element={guarded(null, <ReportPage />)} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

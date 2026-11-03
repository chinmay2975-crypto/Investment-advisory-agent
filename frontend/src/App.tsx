import { Loader2 } from "lucide-react";
import { lazy, type ReactNode, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { Layout } from "@/components/Layout";
import LoginPage from "@/pages/LoginPage";

const AccountPage = lazy(() => import("@/pages/AccountPage"));
const AdvicePage = lazy(() => import("@/pages/AdvicePage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const GoalsPage = lazy(() => import("@/pages/GoalsPage"));
const MarketPage = lazy(() => import("@/pages/MarketPage"));
const OnboardingPage = lazy(() => import("@/pages/OnboardingPage"));
const PortfolioPage = lazy(() => import("@/pages/PortfolioPage"));
const RecommendationsPage = lazy(() => import("@/pages/RecommendationsPage"));
const ResetPasswordPage = lazy(() => import("@/pages/ResetPasswordPage"));
const ScenariosPage = lazy(() => import("@/pages/ScenariosPage"));
const SelfAssessmentPage = lazy(() => import("@/pages/SelfAssessmentPage"));
const TaxPage = lazy(() => import("@/pages/TaxPage"));

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center text-muted-foreground">
      <Loader2 className="mr-2 size-5 animate-spin" /> Restoring your session…
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "loading") return <FullPageSpinner />;
  if (status === "anonymous") return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const { status } = useAuth();
  return (
    <Routes>
      <Route
        path="/login"
        element={status === "authenticated" ? <Navigate to="/dashboard" replace /> : <LoginPage />}
      />
      <Route path="/forgot-password" element={<Suspense fallback={<FullPageSpinner />}><ResetPasswordPage /></Suspense>} />
      <Route path="/reset-password" element={<Suspense fallback={<FullPageSpinner />}><ResetPasswordPage /></Suspense>} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="onboarding" element={<OnboardingPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="advice" element={<AdvicePage />} />
        <Route path="recommendations" element={<RecommendationsPage />} />
        <Route path="goals" element={<GoalsPage />} />
        <Route path="scenarios" element={<ScenariosPage />} />
        <Route path="tax" element={<TaxPage />} />
        <Route path="market" element={<MarketPage />} />
        <Route path="self-assessment" element={<SelfAssessmentPage />} />
        <Route path="account" element={<AccountPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

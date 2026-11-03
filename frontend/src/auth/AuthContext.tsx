import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { login, refreshAccessToken, signup, tokenStore } from "@/api/auth";

type Status = "loading" | "authenticated" | "anonymous";

type AuthValue = {
  status: Status;
  investorId: number | null;
  login: typeof login;
  signup: typeof signup;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>(() => (tokenStore.getRefresh() ? "loading" : "anonymous"));
  const [investorId, setInvestorId] = useState<number | null>(() => tokenStore.getInvestorId());

  useEffect(() => {
    // Restore a session after reload: exchange the stored refresh token for an access token.
    if (tokenStore.getRefresh()) {
      refreshAccessToken().then((ok) => setStatus(ok ? "authenticated" : "anonymous"));
    }
  }, []);

  useEffect(
    () =>
      tokenStore.subscribe(() => {
        const loggedIn = tokenStore.getRefresh() !== null;
        setInvestorId(tokenStore.getInvestorId());
        setStatus(loggedIn ? "authenticated" : "anonymous");
        if (!loggedIn) queryClient.clear();
      }),
    [queryClient],
  );

  const value = useMemo<AuthValue>(
    () => ({ status, investorId, login, signup, logout: () => tokenStore.clear() }),
    [status, investorId],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

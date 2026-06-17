import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  changePassword as changePasswordRequest,
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  type ChangePasswordPayload,
  type LoginPayload,
  type RegisterPayload,
  ApiError,
} from "@/lib/api";
import type { AuthUser } from "@/lib/types";
import { AuthContext } from "./auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const current = await getCurrentUser();
      setUser(current);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
      } else {
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (payload: LoginPayload) => {
    const response = await loginRequest(payload);
    setUser(response.user);
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    const response = await registerRequest(payload);
    setUser(response.user);
  }, []);

  const changePassword = useCallback(async (payload: ChangePasswordPayload) => {
    const nextUser = await changePasswordRequest(payload);
    setUser(nextUser);
  }, []);

  const logout = useCallback(async () => {
    await logoutRequest();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, changePassword, logout, refresh }),
    [changePassword, loading, login, logout, refresh, register, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

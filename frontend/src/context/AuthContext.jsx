import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import {
  login as apiLogin,
  signup as apiSignup,
  logout as apiLogout,
  fetchProfile,
} from '../api';
import { refreshAccessToken, setAccessToken } from '../apiClient';

const AuthContext = createContext(null);

/**
 * Global auth state.
 *
 * On mount we attempt a silent re-auth: the access token is memory-only, so
 * after a page reload we ask the backend to refresh it via the httpOnly
 * cookie, then fetch the profile. If that fails we're simply unauthenticated.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await refreshAccessToken();
        const profile = await fetchProfile();
        if (!cancelled) setUser(profile);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (identifier, password, rememberMe) => {
    const data = await apiLogin(identifier, password, rememberMe);
    setAccessToken(data.access);
    setUser(data.user);
    return data;
  }, []);

  const signup = useCallback(async (username, email, password) => {
    const data = await apiSignup(username, email, password);
    setAccessToken(data.access);
    setUser(data.user);
    return data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Even if the blacklist call fails, we clear local state.
    }
    setAccessToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const profile = await fetchProfile();
    setUser(profile);
    return profile;
  }, []);

  const value = {
    user,
    isAuthenticated: !!user,
    loading,
    login,
    signup,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
import { createContext, useContext, useState, useCallback } from "react";

// ─────────────────────────────────────────────
// CONTEXT SHAPE
// ─────────────────────────────────────────────
const AuthContext = createContext({
  user: null,          // { sub, email, name, picture }
  isLoading: true,
  login: async () => {},
  logout: () => {},
});

const STORAGE_KEY = "sakina_user";

// ─────────────────────────────────────────────
// PROVIDER
// ─────────────────────────────────────────────
export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed?.sub) return parsed;
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
    return null;
  });
  const [isLoading] = useState(false);

  /**
   * login — called after Google returns a credential (ID token).
   * Sends token to the backend for verification, then stores the
   * verified profile locally.
   * @param {string} credential — Google JWT ID token
   * @returns {Promise<{ok: boolean, error?: string}>}
   */
  const login = useCallback(async (credential) => {
    try {
      const res = await fetch("/api/auth/verify", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ token: credential }),
      });

      if (!res.ok) {
        const { detail } = await res.json().catch(() => ({}));
        return { ok: false, error: detail || "Verification failed" };
      }

      const profile = await res.json();   // { sub, email, name, picture }
      setUser(profile);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
      return { ok: true };
    } catch {
      return { ok: false, error: "Network error — please try again." };
    }
  }, []);

  /**
   * logout — clears user state and localStorage.
   */
  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// ─────────────────────────────────────────────
// HOOK
// ─────────────────────────────────────────────
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";

interface User {
  user_id: string;
  email: string;
  name: string;
  org_id: string;
  org_name: string;
  role: string;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  user: User;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (
    email: string,
    password: string,
    name: string,
    orgName: string,
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "indusai_access_token";
const REFRESH_KEY = "indusai_refresh_token";
const USER_KEY = "indusai_user";

function saveTokens(tokens: AuthTokens) {
  localStorage.setItem(TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(tokens.user));
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

function getStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(getStoredUser);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem(TOKEN_KEY),
  );
  const [isLoading, setIsLoading] = useState(true);

  // Verify token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    if (!storedToken) {
      setIsLoading(false);
      return;
    }

    fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Invalid token");
        return res.json();
      })
      .then((data) => {
        setUser(data.user);
        setToken(storedToken);
      })
      .catch(() => {
        // Try refresh
        const refreshToken = localStorage.getItem(REFRESH_KEY);
        if (refreshToken) {
          return fetch("/api/auth/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
          })
            .then((res) => {
              if (!res.ok) throw new Error("Refresh failed");
              return res.json();
            })
            .then((tokens: AuthTokens) => {
              saveTokens(tokens);
              setUser(tokens.user);
              setToken(tokens.access_token);
            })
            .catch(() => {
              clearTokens();
              setUser(null);
              setToken(null);
            });
        }
        clearTokens();
        setUser(null);
        setToken(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  // Auto-refresh every 10 minutes
  useEffect(() => {
    if (!token) return;
    const interval = setInterval(
      () => {
        const refreshToken = localStorage.getItem(REFRESH_KEY);
        if (!refreshToken) return;

        fetch("/api/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
          .then((res) => {
            if (!res.ok) throw new Error("Refresh failed");
            return res.json();
          })
          .then((tokens: AuthTokens) => {
            saveTokens(tokens);
            setToken(tokens.access_token);
            setUser(tokens.user);
          })
          .catch(() => {
            clearTokens();
            setUser(null);
            setToken(null);
          });
      },
      10 * 60 * 1000,
    );
    return () => clearInterval(interval);
  }, [token]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Login failed");
    }
    const tokens: AuthTokens = await res.json();
    saveTokens(tokens);
    setUser(tokens.user);
    setToken(tokens.access_token);
  }, []);

  const signup = useCallback(
    async (
      email: string,
      password: string,
      name: string,
      orgName: string,
    ) => {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          name,
          org_name: orgName,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Signup failed");
      }
      const tokens: AuthTokens = await res.json();
      saveTokens(tokens);
      setUser(tokens.user);
      setToken(tokens.access_token);
    },
    [],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setToken(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, token, isLoading, login, signup, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

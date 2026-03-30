import { create } from "zustand";
import { AuthUser, AuthStatus } from "@/types";
import { API_URL, SKIP_AUTH } from "@/lib/config";

interface DeviceCode {
  user_code: string;
  verification_uri_complete: string;
}

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AuthUser | null;
  expiresIn: number | null;
  skipAuth: boolean;

  // Device flow
  deviceCode: DeviceCode | null;
  isPolling: boolean;
  loginError: string | null;

  // Actions
  checkStatus: () => Promise<void>;
  startLogin: () => Promise<void>;
  pollForToken: () => Promise<"pending" | "success" | "expired" | "error">;
  cancelLogin: () => void;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  isAuthenticated: false,
  isLoading: !SKIP_AUTH,
  user: null,
  expiresIn: null,
  skipAuth: SKIP_AUTH,

  deviceCode: null,
  isPolling: false,
  loginError: null,

  checkStatus: async () => {
    if (SKIP_AUTH) {
      set({ isAuthenticated: true, isLoading: false });
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/axet/auth/status`);
      if (!res.ok) {
        set({ isAuthenticated: false, isLoading: false });
        return;
      }
      const data: AuthStatus = await res.json();

      if (data.authenticated) {
        set({
          isAuthenticated: true,
          isLoading: false,
          user: data.user || null,
          expiresIn: data.expires_in || null,
        });
        return;
      }

      // Token expired but has refresh token — try auto-refresh
      if (data.expired && data.has_refresh_token) {
        try {
          const refreshRes = await fetch(`${API_URL}/api/axet/auth/refresh`, { method: "POST" });
          if (refreshRes.ok) {
            // Recheck after refresh
            const recheckRes = await fetch(`${API_URL}/api/axet/auth/status`);
            if (recheckRes.ok) {
              const recheckData: AuthStatus = await recheckRes.json();
              if (recheckData.authenticated) {
                set({
                  isAuthenticated: true,
                  isLoading: false,
                  user: recheckData.user || null,
                  expiresIn: recheckData.expires_in || null,
                });
                return;
              }
            }
          }
        } catch {
          // Refresh failed, fall through to unauthenticated
        }
      }

      set({ isAuthenticated: false, isLoading: false });
    } catch {
      set({ isAuthenticated: false, isLoading: false });
    }
  },

  startLogin: async () => {
    set({ loginError: null, deviceCode: null });
    try {
      const res = await fetch(`${API_URL}/api/axet/auth/start`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        set({ loginError: data.detail || "Error al iniciar login" });
        return;
      }
      const data = await res.json();
      set({
        deviceCode: {
          user_code: data.user_code,
          verification_uri_complete: data.verification_uri_complete,
        },
        isPolling: true,
        loginError: null,
      });
    } catch (e) {
      set({ loginError: "Error de red al conectar con OKTA" });
    }
  },

  pollForToken: async () => {
    try {
      const res = await fetch(`${API_URL}/api/axet/auth/poll`, { method: "POST" });
      if (!res.ok) return "error";
      const data = await res.json();

      if (data.status === "success") {
        // Login successful — set auth state
        set({
          isAuthenticated: true,
          isPolling: false,
          deviceCode: null,
          user: data.user || null,
          expiresIn: data.expires_in || null,
          loginError: null,
        });

        // Auto-set Axet as the agent provider
        try {
          await fetch(`${API_URL}/api/config/agent`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: "axet" }),
          });
        } catch {
          // Non-critical: config will default to whatever was set
        }

        return "success";
      }

      if (data.status === "expired") {
        set({ isPolling: false, deviceCode: null, loginError: "Codigo expirado. Intenta de nuevo." });
        return "expired";
      }

      if (data.status === "error") {
        set({ isPolling: false, deviceCode: null, loginError: data.message || "Error de autenticacion" });
        return "error";
      }

      return "pending";
    } catch {
      return "error";
    }
  },

  cancelLogin: () => {
    set({ deviceCode: null, isPolling: false, loginError: null });
  },

  logout: async () => {
    try {
      await fetch(`${API_URL}/api/axet/auth/logout`, { method: "POST" });
    } catch {
      // Clear local state even if backend call fails
    }
    set({
      isAuthenticated: false,
      user: null,
      expiresIn: null,
      deviceCode: null,
      isPolling: false,
      loginError: null,
    });
  },
}));

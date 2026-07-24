export interface StoredUser {
  id: string;
  email: string;
  name?: string;
  company?: string;
  plan_tier: string;
  credits_balance: number;
}

const TOKEN_KEY = "market_twin_token";
const USER_KEY = "market_twin_user";
export const AUTH_EVENT = "market-twin-auth";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    clearAuthSession();
    return null;
  }
}

export function saveAuthSession(user: StoredUser, token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: user }));
}

export function updateStoredUser(user: StoredUser): void {
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: user }));
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: null }));
}

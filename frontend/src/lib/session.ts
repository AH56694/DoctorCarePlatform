import type { AccountRead } from "../types";

const currentSessionKey = "doctor-care-platform-current-session";
export const sessionExpiredEvent = "doctorcare:session-expired";

type StoredSession = {
  access_token: string;
  account: AccountRead;
  saved_at: string;
};

export function loadCurrentSession(): StoredSession | null {
  try {
    // Old releases persisted tokens and clinical profiles across browser sessions.
    localStorage.removeItem(currentSessionKey);
    const raw = sessionStorage.getItem(currentSessionKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredSession>;
    if (!parsed.access_token || !parsed.account || typeof parsed.account.id !== "string"
      || typeof parsed.account.phone !== "string") return null;
    return parsed as StoredSession;
  } catch {
    return null;
  }
}

export function saveCurrentSession(account: AccountRead, accessToken?: string) {
  const token = accessToken ?? loadCurrentSession()?.access_token;
  if (!token) return;
  const session: StoredSession = {
    access_token: token,
    // Restore the complete profile from the authenticated API, never browser storage.
    account: {
      id: account.id, phone: account.phone, display_name: account.display_name,
      status: account.status, active_role: account.active_role, roles: account.roles,
      patient_profile: null, caregiver_profile: null, certifications: []
    },
    saved_at: new Date().toISOString()
  };
  sessionStorage.setItem(currentSessionKey, JSON.stringify(session));
}

export function clearCurrentSession() {
  sessionStorage.removeItem(currentSessionKey);
  localStorage.removeItem(currentSessionKey);
}

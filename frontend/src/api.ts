import type { Claim, ClaimDocument, ClaimSummary, ClaimStatus, ClaimType, DocumentType, Paginated, User } from "./types";

const ACCESS_KEY = "cdp_access_token";
const REFRESH_KEY = "cdp_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData) && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api${path}`, { ...options, headers });

  if (response.status === 401 && retry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) return request<T>(path, options, false);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function tryRefreshToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const response = await fetch("/api/auth/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    clearTokens();
    return false;
  }
  const data = await response.json();
  localStorage.setItem(ACCESS_KEY, data.access);
  return true;
}

export async function login(email: string, password: string): Promise<{ user: User; access: string; refresh: string }> {
  const response = await fetch("/api/auth/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body);
  }
  const data = await response.json();
  setTokens(data.access, data.refresh);
  return data;
}

export function logout() {
  clearTokens();
}

export function fetchMe() {
  return request<User>("/auth/me/");
}

export function fetchClaims() {
  return request<Paginated<Claim>>("/claims/");
}

export function fetchClaim(id: number) {
  return request<Claim>(`/claims/${id}/`);
}

export function createClaim(payload: {
  claimant_name: string;
  policy_number: string;
  claim_type: ClaimType;
  narrative_text?: string;
}) {
  return request<Claim>("/claims/", { method: "POST", body: JSON.stringify(payload) });
}

export function updateClaimStatus(id: number, status: ClaimStatus) {
  return request<Claim>(`/claims/${id}/`, { method: "PATCH", body: JSON.stringify({ status }) });
}

export function deleteClaim(id: number) {
  return request<void>(`/claims/${id}/`, { method: "DELETE" });
}

export function uploadDocument(claimId: number, file: File, documentType: DocumentType) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);
  return request<ClaimDocument>(`/claims/${claimId}/documents/`, { method: "POST", body: formData });
}

export function generateSummary(claimId: number) {
  return request<ClaimSummary>(`/claims/${claimId}/generate-summary/`, { method: "POST" });
}

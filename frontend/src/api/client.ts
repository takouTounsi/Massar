const TOKEN_STORAGE_KEY = "massar.access_token";

function readStoredToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

// Rehydrate synchronously at module load (before React renders / the route
// guard evaluates) so a hard refresh on a protected page keeps the session.
let accessToken: string | null = readStoredToken();
const listeners = new Set<() => void>();

export const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5050";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    /* storage unavailable (private mode / SSR) — fall back to in-memory only */
  }
  listeners.forEach((listener) => listener());
}

export function subscribeToToken(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function errorMessage(body: string, fallback: string) {
  if (!body) return fallback;
  try {
    const payload = JSON.parse(body) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
            return item.msg;
          }
          return JSON.stringify(item);
        })
        .join(", ");
    }
  } catch {
    return body;
  }
  return body;
}

/**
 * Multipart upload via XHR so we get real upload progress events. We must NOT
 * set Content-Type here — the browser sets it (with the multipart boundary)
 * from the FormData. Auth + cookies mirror request().
 */
export function uploadFile<T>(
  path: string,
  formData: FormData,
  onProgress?: (percent: number) => void
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${baseUrl}${path}`);
    xhr.withCredentials = true;
    if (accessToken) {
      xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
    }
    xhr.upload.onprogress = (event) => {
      if (onProgress && event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve((xhr.responseText ? JSON.parse(xhr.responseText) : undefined) as T);
        } catch {
          reject(new ApiError("Invalid server response", xhr.status));
        }
      } else {
        reject(new ApiError(errorMessage(xhr.responseText, xhr.statusText), xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("Network error during upload", 0));
    xhr.send(formData);
  });
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(errorMessage(body, response.statusText), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

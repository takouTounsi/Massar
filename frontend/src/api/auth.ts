import { request, setAccessToken } from "./client";
import type { AuthResponse, User } from "./types";

export async function register(payload: { email: string; full_name: string; password: string }) {
  return request<User>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function login(payload: { email: string; password: string }) {
  const response = await request<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  if (response.access_token) {
    setAccessToken(response.access_token);
  }
  return response;
}

export async function refreshSession() {
  const response = await request<AuthResponse>("/api/v1/auth/refresh", {
    method: "POST",
    body: JSON.stringify({})
  });
  if (response.access_token) {
    setAccessToken(response.access_token);
  }
  return response;
}

export async function logout() {
  await request<{ message: string }>("/api/v1/auth/logout", { method: "POST" });
  setAccessToken(null);
}

export function getMe() {
  return request<User>("/api/v1/auth/me");
}

export function changePassword(payload: { current_password: string; new_password: string }) {
  return request<{ message: string }>("/api/v1/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function setup2FA() {
  return request<{ otpauth_uri: string; secret: string; manual_entry_key: string }>("/api/v1/auth/2fa/setup", {
    method: "POST"
  });
}

export function confirm2FA(code: string) {
  return request<User>("/api/v1/auth/2fa/confirm", {
    method: "POST",
    body: JSON.stringify({ code })
  });
}

export async function verify2FA(payload: { temporary_login_token: string; code: string }) {
  const response = await request<AuthResponse>("/api/v1/auth/2fa/verify", {
    method: "POST",
    body: JSON.stringify(payload)
  });
  if (response.access_token) {
    setAccessToken(response.access_token);
  }
  return response;
}

export function disable2FA(code: string) {
  return request<User>("/api/v1/auth/2fa/disable", {
    method: "POST",
    body: JSON.stringify({ code })
  });
}

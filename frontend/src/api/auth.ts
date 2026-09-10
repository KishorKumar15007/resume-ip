import type { LoginRequest, SignupRequest, TokenResponse } from "./contracts";
import { request } from "./client";

export function login(payload: LoginRequest, signal?: AbortSignal): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload), signal });
}

export function signup(payload: SignupRequest, signal?: AbortSignal): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/signup", { method: "POST", body: JSON.stringify(payload), signal });
}

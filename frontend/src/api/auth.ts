import type {
  LoginRequest,
  LoginResponse,
  MFACodeRequest,
  MFASetupResponse,
  MFAVerifyRequest,
  SignupRequest,
  TokenResponse,
} from "./contracts";
import { request } from "./client";

export function login(payload: LoginRequest, signal?: AbortSignal): Promise<LoginResponse> {
  return request<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload), signal });
}

export function signup(payload: SignupRequest, signal?: AbortSignal): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/signup", { method: "POST", body: JSON.stringify(payload), signal });
}

export function setupMfa(token: string, signal?: AbortSignal): Promise<MFASetupResponse> {
  return request<MFASetupResponse>("/auth/mfa/setup", { method: "POST", token, signal });
}

export function confirmMfa(token: string, payload: MFACodeRequest, signal?: AbortSignal): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/mfa/confirm", { method: "POST", token, body: JSON.stringify(payload), signal });
}

export function verifyMfa(payload: MFAVerifyRequest, signal?: AbortSignal): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/mfa/verify", { method: "POST", body: JSON.stringify(payload), signal });
}

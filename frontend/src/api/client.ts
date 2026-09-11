export type ApiErrorKind = "authentication" | "permission" | "notFound" | "validation" | "conflict" | "unavailable" | "unexpected";

export class ApiError extends Error {
  constructor(
    public readonly kind: ApiErrorKind,
    public readonly status?: number,
  ) {
    super(messageFor(kind));
    this.name = "ApiError";
  }
}

let authenticationFailureHandler: ((token: string) => void) | undefined;

export function setAuthenticationFailureHandler(handler: ((token: string) => void) | undefined): void {
  authenticationFailureHandler = handler;
}

function messageFor(kind: ApiErrorKind): string {
  switch (kind) {
    case "authentication": return "Your session is no longer valid. Please sign in again.";
    case "permission": return "You do not have permission to perform this action.";
    case "notFound": return "This posting is no longer available.";
    case "validation": return "Please review the highlighted information and try again.";
    case "conflict": return "This action conflicts with existing information.";
    case "unavailable": return "The service is unavailable. Please try again.";
    default: return "Something went wrong. Please try again.";
  }
}

function resolveApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (!configured) return "/api";
  const url = new URL(configured, window.location.origin);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("VITE_API_BASE_URL must be an http(s) URL without credentials, query, or fragment");
  }
  return url.toString().replace(/\/$/, "");
}

const apiBase = resolveApiBase();

function classifyError(status: number): ApiErrorKind {
  if (status === 401) return "authentication";
  if (status === 403) return "permission";
  if (status === 404) return "notFound";
  if (status === 409) return "conflict";
  if (status === 422) return "validation";
  return "unexpected";
}

interface RequestOptions extends Omit<RequestInit, "body" | "headers"> {
  body?: BodyInit | null;
  token?: string;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers();
  if (options.token) headers.set("Authorization", `Bearer ${options.token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, { ...options, headers });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("unavailable");
  }

  if (!response.ok) {
    if (response.status === 401 && options.token) authenticationFailureHandler?.(options.token);
    throw new ApiError(classifyError(response.status), response.status);
  }
  if (response.status === 204) return undefined as T;

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("unexpected", response.status);
  }
}

import type { ApiErrorShape } from "./types";

export class ApiError extends Error {
  status: number;
  code?: string | number;
  detail?: string;

  constructor(message: string, status: number, body?: ApiErrorShape) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = body?.code;
    this.detail = body?.detail ?? body?.message;
  }
}

const API_BASE = import.meta.env.VITE_API_BASE?.trim() ?? "";

const toUrl = (path: string): string => {
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE.replace(/\/$/, "")}${path}`;
};

const parseErrorBody = async (response: Response): Promise<ApiErrorShape> => {
  const contentType = response.headers.get("content-type") ?? "";
  try {
    if (contentType.includes("application/json")) {
      return (await response.json()) as ApiErrorShape;
    }
    const text = await response.text();
    return { detail: text || response.statusText };
  } catch {
    return { detail: response.statusText };
  }
};

const withJsonHeaders = (init?: RequestInit): RequestInit => {
  const headers = new Headers(init?.headers ?? {});
  if (!(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  return {
    ...init,
    headers,
  };
};

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(toUrl(path), withJsonHeaders(init));
  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(
      body.detail || body.message || response.statusText || "请求失败",
      response.status,
      body,
    );
  }

  if (response.status === 204) {
    return null as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}

export async function requestStream(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const response = await fetch(toUrl(path), withJsonHeaders(init));
  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new ApiError(
      body.detail || body.message || response.statusText || "请求失败",
      response.status,
      body,
    );
  }
  return response;
}

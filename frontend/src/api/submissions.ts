import { request } from "./client";
import type { SubmissionResponse } from "./contracts";

export function getSubmission(token: string, submissionId: string, signal?: AbortSignal): Promise<SubmissionResponse> {
  return request<SubmissionResponse>(`/submissions/${submissionId}`, { token, signal });
}

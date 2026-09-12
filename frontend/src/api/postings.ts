import { request } from "./client";
import type { PostingInput, PostingResponse, RankedSubmissionResponse, SubmissionUploadResponse } from "./contracts";

export function listPostings(token: string, signal?: AbortSignal): Promise<PostingResponse[]> {
  return request<PostingResponse[]>("/postings", { token, signal });
}

export function getPosting(token: string, postingId: string, signal?: AbortSignal): Promise<PostingResponse> {
  return request<PostingResponse>(`/postings/${postingId}`, { token, signal });
}

export function createPosting(token: string, posting: PostingInput): Promise<PostingResponse> {
  return request<PostingResponse>("/postings", { method: "POST", token, body: JSON.stringify(posting) });
}

export function updatePosting(token: string, postingId: string, posting: PostingInput): Promise<PostingResponse> {
  return request<PostingResponse>(`/postings/${postingId}`, { method: "PUT", token, body: JSON.stringify(posting) });
}

export function deletePosting(token: string, postingId: string): Promise<void> {
  return request<void>(`/postings/${postingId}`, { method: "DELETE", token });
}

export function uploadResume(token: string, postingId: string, resume: File, signal?: AbortSignal): Promise<SubmissionUploadResponse> {
  const body = new FormData();
  body.append("resume", resume);
  return request<SubmissionUploadResponse>(`/postings/${postingId}/submissions`, { method: "POST", token, body, signal });
}

export function listRankedSubmissions(token: string, postingId: string, signal?: AbortSignal): Promise<RankedSubmissionResponse[]> {
  return request<RankedSubmissionResponse[]>(`/postings/${postingId}/submissions?sort=score`, { token, signal });
}

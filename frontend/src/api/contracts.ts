export type UserRole = "candidate" | "recruiter";

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest extends LoginRequest {
  role: UserRole;
}

export interface PostingResponse {
  id: string;
  recruiter_id: string;
  title: string;
  description: string;
  required_skills: string[];
  created_at: string;
  updated_at: string;
}

export type SubmissionStatus = "QUEUED" | "PROCESSING" | "DONE" | "FAILED";

export interface SubmissionResponse {
  id: string;
  status: SubmissionStatus;
  score: string | null;
  matched_skills: string[] | null;
}

export interface RankedSubmissionResponse extends SubmissionResponse {
  candidate_id: string;
}

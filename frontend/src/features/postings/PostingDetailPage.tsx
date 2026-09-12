import { type FormEvent, useEffect, useRef, useState } from "react";
import { useParams } from "react-router";

import { ApiError } from "../../api/client";
import type { PostingResponse, SubmissionResponse, SubmissionStatus, SubmissionUploadResponse } from "../../api/contracts";
import { getPosting, uploadResume } from "../../api/postings";
import { getSubmission } from "../../api/submissions";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";
import { FormField } from "../../components/FormField";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; posting: PostingResponse };

type UploadState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "error"; message: string };

interface UploadFailure {
  fieldError?: string;
  message?: string;
}

function describeUploadFailure(error: unknown): UploadFailure {
  if (!(error instanceof ApiError)) return { message: "Something went wrong. Please try again." };

  switch (error.kind) {
    case "authentication":
      return { message: "Your session is no longer valid. Please sign in again." };
    case "permission":
      return { message: "Only candidate accounts can submit a resume for this posting." };
    case "notFound":
      return { message: "This posting is no longer available." };
    case "validation":
      return { fieldError: "That file was not accepted. Choose a valid PDF resume and try again." };
    case "conflict":
      return { message: "You have already submitted a resume for this posting." };
    case "unavailable":
      return { message: "The service is unavailable. Please try again." };
    default:
      return { message: "Something went wrong. Please try again." };
  }
}

function isQueuedSubmission(response: SubmissionUploadResponse): boolean {
  return typeof response.id === "string" && response.id.length > 0 && response.status === "QUEUED";
}

function isSubmissionResponse(response: SubmissionResponse): boolean {
  const validStatuses: SubmissionStatus[] = ["QUEUED", "PROCESSING", "DONE", "FAILED"];
  return typeof response.id === "string"
    && validStatuses.includes(response.status)
    && (typeof response.score === "string" || response.score === null)
    && (response.matched_skills === null || response.matched_skills.every((skill) => typeof skill === "string"));
}

function describeStatusFailure(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong while checking your submission. Please try again.";

  switch (error.kind) {
    case "authentication":
      return "Your session is no longer valid. Please sign in again.";
    case "permission":
      return "You do not have permission to view this submission.";
    case "notFound":
      return "This submission is no longer available.";
    case "unavailable":
      return "The service is unavailable. Please try again.";
    default:
      return "Something went wrong while checking your submission. Please try again.";
  }
}

function formatScore(score: string | null): string | null {
  if (score === null) return null;
  const value = Number(score);
  if (!Number.isFinite(value)) return null;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
}

export function PostingDetailPage() {
  const { postingId } = useParams();
  const { session } = useAuth();
  const [loadState, setLoadState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string>();
  const [uploadState, setUploadState] = useState<UploadState>({ kind: "idle" });
  const [submission, setSubmission] = useState<SubmissionResponse | null>(null);
  const [statusError, setStatusError] = useState<string>();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const uploadControllerRef = useRef<AbortController | null>(null);
  const uploadInFlightRef = useRef(false);
  const statusControllerRef = useRef<AbortController | null>(null);
  const statusInFlightRef = useRef(false);

  useEffect(() => {
    uploadControllerRef.current?.abort();
    uploadControllerRef.current = null;
    uploadInFlightRef.current = false;
    statusControllerRef.current?.abort();
    statusControllerRef.current = null;
    statusInFlightRef.current = false;
    setSelectedFile(null);
    setFileError(undefined);
    setUploadState({ kind: "idle" });
    setSubmission(null);
    setStatusError(undefined);
    setIsRefreshing(false);
  }, [postingId]);

  useEffect(() => () => {
    uploadControllerRef.current?.abort();
    statusControllerRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!postingId) {
      setLoadState({ kind: "error", message: "This posting is no longer available." });
      return;
    }
    const controller = new AbortController();
    setLoadState({ kind: "loading" });
    void getPosting(session!.token, postingId, controller.signal)
      .then((posting) => setLoadState({ kind: "ready", posting }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadState({ kind: "error", message: error instanceof ApiError ? error.message : "Something went wrong. Please try again." });
      });
    return () => controller.abort();
  }, [attempt, postingId, session]);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (uploadInFlightRef.current || submission) return;

    if (!selectedFile) {
      setFileError("Choose a PDF resume to upload.");
      return;
    }

    if (!postingId) {
      setUploadState({ kind: "error", message: "This posting is no longer available." });
      return;
    }

    const controller = new AbortController();
    uploadControllerRef.current = controller;
    uploadInFlightRef.current = true;
    setFileError(undefined);
    setUploadState({ kind: "submitting" });

    try {
      const response = await uploadResume(session!.token, postingId, selectedFile, controller.signal);
      if (!isQueuedSubmission(response)) throw new ApiError("unexpected");
      setSubmission({ id: response.id, status: response.status, score: null, matched_skills: null });
      setStatusError(undefined);
      setUploadState({ kind: "idle" });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const failure = describeUploadFailure(error);
      setFileError(failure.fieldError);
      setUploadState(failure.message ? { kind: "error", message: failure.message } : { kind: "idle" });
    } finally {
      if (uploadControllerRef.current === controller) uploadControllerRef.current = null;
      uploadInFlightRef.current = false;
    }
  }

  async function refreshSubmissionStatus() {
    if (!submission || statusInFlightRef.current) return;

    const controller = new AbortController();
    statusControllerRef.current = controller;
    statusInFlightRef.current = true;
    setStatusError(undefined);
    setIsRefreshing(true);

    try {
      const response = await getSubmission(session!.token, submission.id, controller.signal);
      if (!isSubmissionResponse(response)) throw new ApiError("unexpected");
      setSubmission(response);
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setStatusError(describeStatusFailure(error));
    } finally {
      if (statusControllerRef.current === controller) statusControllerRef.current = null;
      statusInFlightRef.current = false;
      setIsRefreshing(false);
    }
  }

  const isSubmitting = uploadState.kind === "submitting";
  const formattedScore = submission?.status === "DONE" ? formatScore(submission.score) : null;

  return <section className="postings-page" aria-labelledby="posting-title">
    {loadState.kind === "loading" && <><h1 id="posting-title">Posting details</h1><Feedback>Loading posting…</Feedback></>}
    {loadState.kind === "error" && <div className="page-feedback">
      <h1 id="posting-title">Posting unavailable</h1>
      <Feedback tone="error">{loadState.message}</Feedback>
      {postingId && <Button type="button" variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</Button>}
    </div>}
    {loadState.kind === "ready" && <>
      <p className="eyebrow">Open role</p>
      <h1 id="posting-title">{loadState.posting.title}</h1>
      <div className="posting-detail">
        <div>
          <h2>About this role</h2>
          <p className="posting-description">{loadState.posting.description}</p>
        </div>
        <div>
          <h2>Required skills</h2>
          <ul className="skill-list">{loadState.posting.required_skills.map((skill) => <li key={skill}>{skill}</li>)}</ul>
        </div>
      </div>
      {session!.role === "candidate" && <section className="resume-upload" aria-labelledby="resume-upload-title">
        <h2 id="resume-upload-title">Submit your resume</h2>
        <p>Choose the PDF resume you want to submit for this role. Accepted files enter the processing queue.</p>
        {uploadState.kind === "error" && <Feedback tone="error">{uploadState.message}</Feedback>}
        <form className="resume-upload__form" noValidate aria-busy={isSubmitting} onSubmit={(event) => void handleUpload(event)}>
          <div aria-live="polite">
            <FormField label="Resume PDF" help="PDF files only." error={fileError}>{(props) => <input {...props} key={postingId} accept=".pdf,application/pdf" disabled={isSubmitting || submission !== null} required type="file" onChange={(event) => {
              setSelectedFile(event.currentTarget.files?.[0] ?? null);
              setFileError(undefined);
              if (uploadState.kind === "error") setUploadState({ kind: "idle" });
            }} />}</FormField>
          </div>
          {selectedFile && <p className="selected-file" aria-live="polite">Selected file: <span>{selectedFile.name}</span></p>}
          <Button type="submit" disabled={isSubmitting || submission !== null}>{isSubmitting ? "Uploading…" : submission ? "Resume submitted" : "Submit resume"}</Button>
        </form>
      </section>}
      {session!.role === "candidate" && submission && <section className="submission-status" aria-labelledby="submission-status-title" aria-busy={isRefreshing}>
        <h2 id="submission-status-title">Resume processing</h2>
        <span className={`status-badge status-badge--${submission.status.toLowerCase()}`}>{submission.status.charAt(0) + submission.status.slice(1).toLowerCase()}</span>
        {submission.status === "QUEUED" && <Feedback>Your resume is queued for processing.</Feedback>}
        {submission.status === "PROCESSING" && <Feedback>Your resume is being processed.</Feedback>}
        {submission.status === "DONE" && <>
          <p className="submission-status__copy">This result compares your resume with this posting’s required skills.</p>
          {formattedScore === null ? <Feedback tone="warning">A compatibility result is not available for this completed submission.</Feedback> : <p className="compatibility-score"><span>Compatibility score</span><strong>{formattedScore}%</strong></p>}
          <div className="matched-skills">
            <h3>Matched skills</h3>
            {submission.matched_skills === null ? <p>Matched skills are not available for this completed submission.</p> : submission.matched_skills.length === 0 ? <p>No required skills were matched.</p> : <ul className="skill-list">{submission.matched_skills.map((skill) => <li key={skill}>{skill}</li>)}</ul>}
          </div>
        </>}
        {submission.status === "FAILED" && <Feedback tone="error">Processing could not be completed. This portal does not offer a retry for this submission.</Feedback>}
        {isRefreshing && <Feedback>Checking the current processing status…</Feedback>}
        {statusError && <div className="page-feedback"><Feedback tone="error">{statusError}</Feedback>{(submission.status === "QUEUED" || submission.status === "PROCESSING") && <Button type="button" variant="secondary" onClick={() => void refreshSubmissionStatus()}>Try again</Button>}</div>}
        {(submission.status === "QUEUED" || submission.status === "PROCESSING") && !statusError && <Button type="button" variant="secondary" disabled={isRefreshing} onClick={() => void refreshSubmissionStatus()}>{isRefreshing ? "Refreshing…" : "Refresh status"}</Button>}
      </section>}
    </>}
  </section>;
}

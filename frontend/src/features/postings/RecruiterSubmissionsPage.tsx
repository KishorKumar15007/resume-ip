import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { ApiError } from "../../api/client";
import type { PostingResponse, RankedSubmissionResponse, SubmissionStatus } from "../../api/contracts";
import { getPosting, listRankedSubmissions } from "../../api/postings";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; posting: PostingResponse; submissions: RankedSubmissionResponse[] };

function statusLabel(status: SubmissionStatus): string {
  return status.charAt(0) + status.slice(1).toLowerCase();
}

function scoreLabel(score: string | null): string {
  if (score === null || score.trim() === "") return "Unavailable";
  const value = Number(score);
  return Number.isFinite(value)
    ? `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)}%`
    : "Unavailable";
}

export function RecruiterSubmissionsPage() {
  const { session } = useAuth();
  const { postingId } = useParams();
  const [loadState, setLoadState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!postingId) {
      setLoadState({ kind: "error", message: "This posting is no longer available." });
      return;
    }

    const controller = new AbortController();
    setLoadState({ kind: "loading" });
    void Promise.all([
      getPosting(session!.token, postingId, controller.signal),
      listRankedSubmissions(session!.token, postingId, controller.signal),
    ]).then(([posting, submissions]) => {
      if (controller.signal.aborted) return;
      setLoadState({ kind: "ready", posting, submissions });
    }).catch((error: unknown) => {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return;
      setLoadState({ kind: "error", message: error instanceof ApiError ? error.message : "Something went wrong. Please try again." });
    });
    return () => controller.abort();
  }, [attempt, postingId, session]);

  return <section className="postings-page recruiter-submissions-page" aria-labelledby="submissions-title">
    <div className="page-heading"><div><p className="eyebrow">Recruiter workspace</p><h1 id="submissions-title">{loadState.kind === "ready" ? `Submissions for ${loadState.posting.title}` : "Ranked submissions"}</h1></div>{loadState.kind === "ready" && <Button type="button" variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Refresh shortlist</Button>}</div>
    {loadState.kind === "loading" && <Feedback>Loading ranked submissions…</Feedback>}
    {loadState.kind === "error" && <div className="page-feedback"><Feedback tone="error">{loadState.message}</Feedback><Button type="button" variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</Button></div>}
    {loadState.kind === "ready" && <>
      <p className="lede">Candidates are ordered by compatibility. Submissions still being processed appear after scored candidates.</p>
      {loadState.submissions.length === 0 ? <Feedback>No candidates have submitted resumes for this posting yet.</Feedback> : <ol className="ranked-submissions" aria-label="Ranked candidate submissions">{loadState.submissions.map((submission, index) => <li key={submission.candidate_id}><article className="ranked-submission">
        <div className="ranked-submission__heading"><p className="submission-rank">Rank {index + 1}</p><span className={`status-badge status-badge--${submission.status.toLowerCase()}`}>{statusLabel(submission.status)}</span></div>
        <h2 className="candidate-label">{submission.candidate_email}</h2>
        {submission.status === "DONE" && <div className="submission-result"><p className="compatibility-score"><span>Compatibility score</span><strong>{scoreLabel(submission.score)}</strong></p><div className="matched-skills"><h3>Matched required skills</h3>{submission.matched_skills === null ? <Feedback tone="warning">Matched skills are unavailable for this completed submission.</Feedback> : submission.matched_skills.length === 0 ? <p>No required skills were matched.</p> : <ul className="skill-list">{submission.matched_skills.map((skill, skillIndex) => <li key={skillIndex}>{skill}</li>)}</ul>}</div></div>}
        {submission.status === "FAILED" && <Feedback tone="warning">Processing failed. No compatibility result is available.</Feedback>}
      </article></li>)}</ol>}
    </>}
  </section>;
}

import { useEffect, useState } from "react";
import { Link } from "react-router";

import { ApiError } from "../../api/client";
import type { PostingResponse } from "../../api/contracts";
import { listPostings } from "../../api/postings";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; postings: PostingResponse[] };

export function CandidatePostingsPage() {
  const { session } = useAuth();
  const [loadState, setLoadState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoadState({ kind: "loading" });
    void listPostings(session!.token, controller.signal)
      .then((postings) => setLoadState({ kind: "ready", postings }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadState({ kind: "error", message: error instanceof ApiError ? error.message : "Something went wrong. Please try again." });
      });
    return () => controller.abort();
  }, [attempt, session]);

  return <section className="postings-page" aria-labelledby="postings-title"><p className="eyebrow">Open roles</p><h1 id="postings-title">Browse postings</h1><p className="lede">Review the available roles and their required skills before submitting a resume.</p>{loadState.kind === "loading" && <Feedback>Loading available postings…</Feedback>}{loadState.kind === "error" && <div className="page-feedback"><Feedback tone="error">{loadState.message}</Feedback><Button type="button" variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</Button></div>}{loadState.kind === "ready" && (loadState.postings.length === 0 ? <Feedback>There are no job postings available right now. Check back when a recruiter adds a role.</Feedback> : <ul className="posting-list">{loadState.postings.map((posting) => <li key={posting.id}><article className="posting-row"><div><h2><Link to={`/postings/${posting.id}`} state={{ parentPath: "/postings" }}>{posting.title}</Link></h2><p>{posting.description}</p><ul className="skill-list" aria-label={`Required skills for ${posting.title}`}>{posting.required_skills.map((skill) => <li key={skill}>{skill}</li>)}</ul></div></article></li>)}</ul>)}</section>;
}

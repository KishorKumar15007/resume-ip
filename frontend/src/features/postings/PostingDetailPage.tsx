import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { ApiError } from "../../api/client";
import type { PostingResponse } from "../../api/contracts";
import { getPosting } from "../../api/postings";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; posting: PostingResponse };

export function PostingDetailPage() {
  const { postingId } = useParams();
  const { session } = useAuth();
  const [loadState, setLoadState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

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

  return <section className="postings-page" aria-labelledby="posting-title">{loadState.kind === "loading" && <Feedback>Loading posting…</Feedback>}{loadState.kind === "error" && <div className="page-feedback"><h1 id="posting-title">Posting unavailable</h1><Feedback tone="error">{loadState.message}</Feedback>{postingId && <Button type="button" variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</Button>}</div>}{loadState.kind === "ready" && <><p className="eyebrow">Open role</p><h1 id="posting-title">{loadState.posting.title}</h1><div className="posting-detail"><div><h2>About this role</h2><p className="posting-description">{loadState.posting.description}</p></div><div><h2>Required skills</h2><ul className="skill-list">{loadState.posting.required_skills.map((skill) => <li key={skill}>{skill}</li>)}</ul></div></div></>}</section>;
}

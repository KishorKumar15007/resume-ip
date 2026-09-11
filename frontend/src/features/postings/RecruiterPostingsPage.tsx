import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { ApiError } from "../../api/client";
import type { PostingResponse } from "../../api/contracts";
import { deletePosting, listPostings } from "../../api/postings";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; postings: PostingResponse[] };

export function RecruiterPostingsPage() {
  const { session } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [loadState, setLoadState] = useState<LoadState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pendingDeletion, setPendingDeletion] = useState<PostingResponse | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const notice = typeof location.state === "object" && location.state !== null && "notice" in location.state && typeof location.state.notice === "string" ? location.state.notice : null;

  useEffect(() => {
    if (notice) navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, navigate, notice]);

  useEffect(() => {
    const controller = new AbortController();
    setLoadState({ kind: "loading" });
    void listPostings(session!.token, controller.signal)
      .then((postings) => {
        // Presentation only: the server remains the authorization boundary.
        setLoadState({ kind: "ready", postings: postings.filter((posting) => posting.recruiter_id === session!.userId) });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadState({ kind: "error", message: error instanceof ApiError ? error.message : "Something went wrong. Please try again." });
      });
    return () => controller.abort();
  }, [attempt, session]);

  async function confirmDelete() {
    if (!pendingDeletion || deletingId) return;
    setActionMessage(null);
    setDeletingId(pendingDeletion.id);
    try {
      await deletePosting(session!.token, pendingDeletion.id);
      setLoadState((current) => current.kind === "ready" ? { kind: "ready", postings: current.postings.filter((item) => item.id !== pendingDeletion.id) } : current);
      setPendingDeletion(null);
      setActionMessage("Posting deleted.");
    } catch (error) {
      setActionMessage(error instanceof ApiError ? error.message : "Something went wrong. Please try again.");
    } finally {
      setDeletingId(null);
    }
  }

  return <section className="postings-page" aria-labelledby="managed-postings-title"><div className="page-heading"><div><p className="eyebrow">Recruiter workspace</p><h1 id="managed-postings-title">Your postings</h1></div><Link className="button button--primary" to="/recruiter/postings/new" state={{ parentPath: "/recruiter/postings" }}>Create posting</Link></div><p className="lede">Create and maintain the roles your candidates can browse.</p>{notice && <Feedback tone="success">{notice}</Feedback>}{actionMessage && <Feedback tone={actionMessage === "Posting deleted." ? "success" : "error"}>{actionMessage}</Feedback>}{loadState.kind === "loading" && <Feedback>Loading your postings…</Feedback>}{loadState.kind === "error" && <div className="page-feedback"><Feedback tone="error">{loadState.message}</Feedback><Button type="button" variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</Button></div>}{loadState.kind === "ready" && (loadState.postings.length === 0 ? <Feedback>You have not created any postings yet. Create a posting to begin receiving applications.</Feedback> : <ul className="posting-list">{loadState.postings.map((posting) => <li key={posting.id}><article className="posting-row"><div><h2>{posting.title}</h2><p>{posting.description}</p><ul className="skill-list" aria-label={`Required skills for ${posting.title}`}>{posting.required_skills.map((skill) => <li key={skill}>{skill}</li>)}</ul></div><div className="posting-row__actions"><Link className="button button--secondary" to={`/recruiter/postings/${posting.id}/edit`} state={{ parentPath: "/recruiter/postings" }}>Edit</Link><Button type="button" variant="secondary" disabled={pendingDeletion !== null} isLoading={deletingId === posting.id} onClick={() => { setActionMessage(null); setPendingDeletion(posting); }}>Delete</Button></div></article>{pendingDeletion?.id === posting.id && <section className="delete-confirmation" aria-labelledby="delete-confirmation-title"><h2 id="delete-confirmation-title">Delete “{posting.title}”?</h2><p>This cannot be undone.</p><div className="delete-confirmation__actions"><Button autoFocus type="button" variant="secondary" disabled={deletingId !== null} onClick={() => setPendingDeletion(null)}>Cancel</Button><Button type="button" isLoading={deletingId === posting.id} onClick={() => void confirmDelete()}>Delete posting</Button></div></section>}</li>)}</ul>)}</section>;
}

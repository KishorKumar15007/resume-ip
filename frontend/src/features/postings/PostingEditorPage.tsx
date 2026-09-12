import { type FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { ApiError } from "../../api/client";
import { createPosting, getPosting, updatePosting } from "../../api/postings";
import { useAuth } from "../../auth/RequireAuth";
import { Button } from "../../components/Button";
import { Feedback } from "../../components/Feedback";
import { FormField } from "../../components/FormField";

type EditorMode = "create" | "edit";

export function PostingEditorPage({ mode }: { mode: EditorMode }) {
  const { postingId } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skillsText, setSkillsText] = useState("");
  const [loading, setLoading] = useState(mode === "edit");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showValidation, setShowValidation] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const requiredSkills = skillsText.split("\n").map((skill) => skill.trim()).filter(Boolean);
  const titleError = title.trim() ? title.trim().length <= 200 ? undefined : "Use 200 characters or fewer." : "Enter a title.";
  const descriptionError = description.trim() ? undefined : "Enter a description.";
  const skillsError = requiredSkills.length > 0 ? undefined : "Enter at least one required skill.";

  useEffect(() => {
    if (mode === "create") return;
    if (!postingId) {
      setLoading(false);
      setLoadError("This posting is no longer available.");
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);
    void getPosting(session!.token, postingId, controller.signal)
      .then((posting) => {
        if (posting.recruiter_id !== session!.userId) {
          navigate("/forbidden", { replace: true });
          return;
        }
        setTitle(posting.title);
        setDescription(posting.description);
        setSkillsText(posting.required_skills.join("\n"));
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadError(error instanceof ApiError ? error.message : "Something went wrong. Please try again.");
        setLoading(false);
      });
    return () => controller.abort();
  }, [attempt, mode, navigate, postingId, session]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setShowValidation(true);
    if (titleError || descriptionError || skillsError) return;
    setSubmitError(null);
    setSubmitting(true);
    const posting = { title: title.trim(), description: description.trim(), required_skills: requiredSkills };
    try {
      if (mode === "create") await createPosting(session!.token, posting);
      else if (postingId) await updatePosting(session!.token, postingId, posting);
      navigate("/recruiter/postings", { replace: true, state: { notice: mode === "create" ? "Posting created." : "Posting updated." } });
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const heading = mode === "create" ? "Create posting" : "Edit posting";
  if (loading) return <section className="posting-editor" aria-labelledby="posting-editor-title"><h1 id="posting-editor-title">{heading}</h1><Feedback>Loading posting…</Feedback></section>;
  if (loadError) return <section className="posting-editor" aria-labelledby="posting-editor-title"><h1 id="posting-editor-title">Posting unavailable</h1><Feedback tone="error">{loadError}</Feedback>{mode === "edit" && <Button type="button" variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</Button>}</section>;

  return <section className="posting-editor" aria-labelledby="posting-editor-title"><p className="eyebrow">Recruiter workspace</p><h1 id="posting-editor-title">{heading}</h1><p className="lede">Describe the role and list each required skill on its own line.</p>{submitError && <Feedback tone="error">{submitError}</Feedback>}<form className="form" noValidate onSubmit={(event) => void handleSubmit(event)}><FormField label="Title" error={showValidation ? titleError : undefined}>{(props) => <input {...props} maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} />}</FormField><FormField label="Description" error={showValidation ? descriptionError : undefined}>{(props) => <textarea {...props} value={description} onChange={(event) => setDescription(event.target.value)} />}</FormField><FormField label="Required skills" help="Enter one skill per line." error={showValidation ? skillsError : undefined}>{(props) => <textarea {...props} value={skillsText} onChange={(event) => setSkillsText(event.target.value)} />}</FormField><div className="form-actions"><Button type="submit" isLoading={submitting}>{mode === "create" ? "Create posting" : "Save changes"}</Button></div></form></section>;
}

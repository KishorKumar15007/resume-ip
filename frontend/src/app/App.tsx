import { Route, Routes } from "react-router";

import { RedirectIfAuthenticated, RequireAuth } from "../auth/RequireAuth";
import { AppShell } from "../components/AppShell";
import { LoginPage } from "../features/auth/LoginPage";
import { SessionPage } from "../features/auth/SessionPage";
import { SignupPage } from "../features/auth/SignupPage";
import { CandidatePostingsPage } from "../features/postings/CandidatePostingsPage";
import { PostingDetailPage } from "../features/postings/PostingDetailPage";
import { PostingEditorPage } from "../features/postings/PostingEditorPage";
import { RecruiterPostingsPage } from "../features/postings/RecruiterPostingsPage";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { LandingPage } from "../pages/LandingPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RouteEffects } from "./RouteEffects";

export function App() {
  return <><RouteEffects /><AppShell><Routes><Route path="/" element={<LandingPage />} /><Route element={<RedirectIfAuthenticated />}><Route path="/login" element={<LoginPage />} /><Route path="/signup" element={<SignupPage />} /></Route><Route element={<RequireAuth />}><Route path="/session" element={<SessionPage />} /><Route path="/postings" element={<CandidatePostingsPage />} /><Route path="/postings/:postingId" element={<PostingDetailPage />} /></Route><Route element={<RequireAuth allowedRoles={["recruiter"]} />}><Route path="/recruiter/postings" element={<RecruiterPostingsPage />} /><Route path="/recruiter/postings/new" element={<PostingEditorPage mode="create" />} /><Route path="/recruiter/postings/:postingId/edit" element={<PostingEditorPage mode="edit" />} /></Route><Route path="/forbidden" element={<ForbiddenPage />} /><Route path="*" element={<NotFoundPage />} /></Routes></AppShell></>;
}

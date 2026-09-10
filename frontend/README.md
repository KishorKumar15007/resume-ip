# Resume Intelligence Portal frontend

This React application provides the portal foundation and working authentication flow. Posting, resume upload, scoring results, and ranked submissions are intentionally deferred.

## Local setup

From `frontend`, use the project-local scripts after dependencies are installed:

```powershell
& 'C:\Program Files\nodejs\node.exe' 'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js' run dev
```

The browser app runs locally and proxies `/api` to `http://127.0.0.1:8000`. Start the FastAPI application separately. The default browser API path is `/api`.

`VITE_API_BASE_URL` can point the browser to an explicit public HTTP(S) API base. `API_PROXY_TARGET` changes the local Vite proxy target. Both reject URLs with credentials, query strings, and fragments. No frontend configuration may contain a secret; Vite dotenv loading is disabled.

## Checks

```powershell
& 'C:\Program Files\nodejs\node.exe' 'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js' run typecheck
& 'C:\Program Files\nodejs\node.exe' 'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js' run build
```

## Manual verification

1. Start the FastAPI application and the frontend development server.
2. Create both candidate and recruiter accounts, then confirm each reaches the signed-in session page.
3. Sign in with valid credentials; check invalid credentials, duplicate signup, and an eight-character password requirement display controlled errors.
4. Sign out, reload the page, open a new tab, and wait for a token to expire; each should require sign-in again.
5. Visit `/session` while signed out, `/forbidden`, and an unknown route; check redirects and return links.
6. Check keyboard navigation, visible focus, screen-reader error feedback, zoom, and mobile/tablet/desktop layouts.
7. Confirm browser storage and URLs contain no password or access token.

Browser/API runtime verification is performed manually and remains unconfirmed until results are reported.

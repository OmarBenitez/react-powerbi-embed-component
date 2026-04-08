# Power BI React + Flask Embed

Minimal React app (Vite + Bootstrap) with a Flask backend that generates Power BI embed tokens from a full report URL.

## Repository Structure

```text
pbireact/
  web/   # React + Vite frontend
  api/   # Flask backend
  README.md
```

## Architecture

- Frontend asks for a full Power BI report URL.
- `PowerBIEmbed` component calls backend `POST /api/powerbi/embed-config`.
- Backend extracts `groupId`, `reportId`, optional `pageName` from the URL.
- Backend authenticates with service principal and calls Power BI `GenerateToken` (v2).
- Frontend embeds the report using `powerbi-client-react`.

## Core Files

- Frontend app entry: `web/src/App.jsx`
- Embed component: `web/src/components/PowerBIEmbed.jsx`
- Frontend styles: `web/src/styles.css`
- Backend API: `api/app.py`

## Backend Routes

### `POST /api/powerbi/embed-config`
Generates embed payload from a full report URL.

Request body:

```json
{
  "reportUrl": "https://app.powerbi.com/groups/<groupId>/reports/<reportId>/..."
}
```

Success response:

```json
{
  "groupId": "...",
  "reportId": "...",
  "datasetId": "...",
  "pageName": "ReportSection...",
  "embedUrl": "https://app.powerbi.com/reportEmbed?...",
  "embedToken": "...",
  "tokenExpiration": "2026-04-08T...Z"
}
```

Error response:

```json
{
  "error": "Power BI API error: ..."
}
```

## Environment Variables

### Frontend (`web/.env`)

```env
VITE_BACKEND_URL=
VITE_DEFAULT_REPORT_URL=
```

Notes:
- Keep `VITE_BACKEND_URL` empty when using local Vite proxy (`/api -> http://127.0.0.1:5000`).
- Set `VITE_DEFAULT_REPORT_URL` if you want a prefilled URL in the input.

### Backend (`api/.env`)

```env
PBI_TENANT_ID=your-tenant-id
PBI_CLIENT_ID=your-client-id
PBI_CLIENT_SECRET=your-client-secret
PBI_EMBED_TOKEN_LIFETIME_MINUTES=
```

Notes:
- `PBI_EMBED_TOKEN_LIFETIME_MINUTES` is optional.
- Backend loads this file directly from `api/.env`.

## Run Locally

From project root:

1. Install frontend dependencies:

```powershell
cd web
npm.cmd install
```

2. Install backend dependencies:

```powershell
cd ..\api
python -m pip install -r requirements.txt
```

3. Start backend:

```powershell
python app.py
```

4. Start frontend (new terminal):

```powershell
cd web
npm.cmd run dev
```

5. Open the frontend URL (usually `http://localhost:5173`), paste a Power BI report URL, click **Load report**.

## If Another Team Wants To Use This In Their Site

1. Copy/reuse `web/src/components/PowerBIEmbed.jsx`.
2. Pass only `reportUrl` to the component.
3. Expose a backend endpoint compatible with `POST /api/powerbi/embed-config`.
4. Set frontend `.env` (`VITE_BACKEND_URL`) to their backend base URL (or keep proxy setup).
5. Set backend `.env` with their own tenant/client/secret.
6. Ensure Power BI tenant/workspace permissions are configured for service principal embed scenarios.

## Common Troubleshooting

- `Only folder user with reshare permissions can generate embed token`
  - Service principal permissions are still insufficient for the target content path.
- `403` / `InvalidRequest` from backend
  - Verify tenant settings and workspace/dataset access for the service principal.
- Report not filling height
  - Keep `web/src/styles.css` iframe rules and full-height layout chain (`html`, `body`, `#root`).

## Build

```powershell
cd web
npm.cmd run build
```

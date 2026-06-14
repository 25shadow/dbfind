# Upload Import Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each selected file immediately in the left library panel with upload percentage, speed, import phase, and final result.

**Architecture:** Keep the backend upload/import flow intact. Replace the frontend bulk call in the library with per-file uploads using `XMLHttpRequest` so upload progress is available, then poll existing file status for import completion.

**Tech Stack:** React 19, TanStack Query, TypeScript, Vite, FastAPI existing file endpoints.

---

### Task 1: Progress-Capable Upload API

**Files:**
- Modify: `apps/web/src/api/http.ts`
- Modify: `apps/web/src/features/files/api.ts`

- [ ] Export `API_BASE_URL` from `http.ts`.
- [ ] Add `uploadFileWithProgress(payload, onProgress)` in `files/api.ts`.
- [ ] Parse non-2xx API errors consistently with existing `apiRequest`.
- [ ] Run `npm run web:typecheck`.

### Task 2: Left-Side Upload Queue

**Files:**
- Modify: `apps/web/src/features/library/components/DriveLibrary.tsx`

- [ ] Replace the single bulk upload mutation with a local upload queue.
- [ ] Add selected files to the queue immediately.
- [ ] Upload files sequentially, updating percent, speed, and stage.
- [ ] Use existing `files` polling to mark queued items ready, needs review, or failed.
- [ ] Keep uploaded/importing queued items visible above the directory rows.
- [ ] Run `npm run web:typecheck`.

### Task 3: Queue Styling

**Files:**
- Modify: `apps/web/src/styles/globals.css`

- [ ] Add compact queue layout.
- [ ] Add progress bars, status pills, speed/remaining text, and failure styling.
- [ ] Ensure long filenames truncate and buttons do not overflow.
- [ ] Run `npm run web:build`.

### Self-Review

- Scope is limited to the visible left-side upload/import experience.
- Backend precision is not changed; import progress is phase-based until the backend exposes job-level progress.
- No placeholders remain in this plan.

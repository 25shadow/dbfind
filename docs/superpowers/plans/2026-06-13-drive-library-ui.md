# Drive Library UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current flat 자료 panel with a drive-style library that supports folder hierarchy, navigation, batch operations, and custom dialogs.

**Architecture:** Keep the existing `collections` table as folders and add `parent_id` for hierarchy. Files keep `collection_id` as their containing folder. The React library UI uses a current-folder state, breadcrumb history, selection state, and reusable app dialogs instead of browser prompts.

**Tech Stack:** FastAPI, SQLite repositories, React, TypeScript, Zustand, TanStack Query, plain CSS.

---

### Task 1: Backend Folder Hierarchy And Moves

**Files:**
- Modify: `apps/api/app/repositories/collection_repository.py`
- Modify: `apps/api/app/repositories/file_repository.py`
- Modify: `apps/api/app/services/collection_service.py`
- Modify: `apps/api/app/schemas/collections.py`
- Modify: `apps/api/app/api/routes/collections.py`
- Test: `apps/api/tests/test_collection_repository.py`

- [ ] Write tests for `parent_id`, listing children, moving collections, and moving files.
- [ ] Run `pytest tests/test_collection_repository.py` and confirm the new tests fail because APIs do not exist yet.
- [ ] Add `parent_id` to `collections` with migration-style `_ensure_column`.
- [ ] Add repository methods `list_children`, `move_collection`, `has_child_collections`, and `move_files`.
- [ ] Add service validation to prevent moving a folder into itself or its descendant.
- [ ] Add API endpoints for children listing and bulk move.
- [ ] Run targeted tests until they pass.

### Task 2: Custom Dialog System

**Files:**
- Create: `apps/web/src/components/dialogs/AppDialog.tsx`
- Create: `apps/web/src/components/dialogs/dialogTypes.ts`
- Modify: `apps/web/src/styles/globals.css`

- [ ] Create a reusable modal shell with title, description, body, cancel, confirm, and danger states.
- [ ] Use fixed positioning and overlay so it is not clipped by scrolling panels.
- [ ] Add accessible `role="dialog"` and `aria-modal="true"`.

### Task 3: Drive-Style Library UI

**Files:**
- Create: `apps/web/src/features/library/components/DriveLibrary.tsx`
- Create: `apps/web/src/features/library/components/MoveDialog.tsx`
- Create: `apps/web/src/features/library/store.ts`
- Modify: `apps/web/src/features/collections/api.ts`
- Modify: `apps/web/src/features/collections/hooks.ts`
- Modify: `apps/web/src/features/collections/types.ts`
- Modify: `apps/web/src/features/files/api.ts`
- Modify: `apps/web/src/features/files/components/FileSidebar.tsx`
- Modify: `apps/web/src/styles/globals.css`

- [ ] Replace `CollectionManager` usage with `DriveLibrary`.
- [ ] Show breadcrumb, back/forward buttons, current folder children, and current folder files.
- [ ] Add checkbox selection for files/folders.
- [ ] Add toolbar actions for new folder, upload, rename, move, delete.
- [ ] Replace all library `window.confirm` calls with `AppDialog`.
- [ ] Keep selecting a file connected to existing Sheet preview and AI selected-file query.

### Task 4: Verification

- [ ] Run `pytest`.
- [ ] Run `python -m compileall apps\api\app apps\api\tests`.
- [ ] Run `npm run web:typecheck`.
- [ ] Search for remaining `window.confirm`, `window.prompt`, and `window.alert`.

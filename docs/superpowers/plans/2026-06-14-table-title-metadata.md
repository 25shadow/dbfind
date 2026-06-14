# Table Title Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse already extracted raw content blocks to persist and display table number, Chinese title, English title, and unit/base metadata for imported sheets.

**Architecture:** The existing structure pipeline already captures titles and units in `rawContentBlocks`. Add a small metadata extractor that derives sheet `title`, `subtitle`, and `unit` from those blocks, write them into the existing `sheets` table, and display them in the sheet preview.

**Tech Stack:** Python, pytest, existing SQLite repositories, React/TypeScript preview components.

---

### Task 1: Metadata Extraction

**Files:**
- Create: `apps/api/app/services/table_metadata_extractor.py`
- Test: `apps/api/tests/test_table_metadata_extractor.py`

- [ ] Extract `title`, `subtitle`, and `unit` from generic raw content blocks without hardcoded table numbers.
- [ ] Recognize title-like first non-empty block, English subtitle-like second block, and unit/base blocks containing `单位`, `unit`, `=100`, or parenthesized English unit text.
- [ ] Verify with `python -m pytest tests/test_table_metadata_extractor.py -q`.

### Task 2: Import Integration

**Files:**
- Modify: `apps/api/app/services/file_service.py`
- Test: `apps/api/tests/test_file_service_import.py`

- [ ] When `_write_structure_results_to_duckdb` creates `sheets`, include extracted `title`, `subtitle`, and `unit`.
- [ ] Ensure existing CSV/basic import behavior remains unchanged.
- [ ] Verify with `python -m pytest tests/test_file_service_import.py -q`.

### Task 3: Preview Display

**Files:**
- Modify: `apps/web/src/features/sheets/components/SheetPreview.tsx`

- [ ] Display sheet title, subtitle, and unit above the database preview table when present.
- [ ] Keep current fallback to sheet name when title is absent.
- [ ] Verify with `npm run build`.

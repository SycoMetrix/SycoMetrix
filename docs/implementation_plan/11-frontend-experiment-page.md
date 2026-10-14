# 11 — Experiment Page

**Phase:** Frontend · **Depends on:** 06, 10 · **Unblocks:** 13 · **Size:** L

## Goal

Build the page for a single experiment at `/experiments/<id>`. From here the user can:

1. Edit the experiment's name and description.
2. Add, view, and delete test cases.
3. Pick a model and **run** the experiment, with live progress.
4. See each test case's status and risk level, and click through to the comparison view.

This page is the heart of the workflow. It's the largest frontend ticket; it can be split into 11a (test case management) and 11b (running) if two people work on it.

## Background

- Endpoints: experiment detail and test cases (ticket 04), `GET /api/models` (05), `POST /api/test-cases/<id>/run` (06).
- Helpers: `api.js` and `dom.js` (ticket 10).
- [Why one test case per request](06-response-collection.md#why-one-test-case-per-request): the browser drives the run loop.

## Files

| File                                    | Change |
|-----------------------------------------|--------|
| `sycometrix/pages.py`                   | Add `/experiments/<int:id>` (404 page if the experiment doesn't exist) |
| `sycometrix/templates/experiment.html`  | Create |
| `sycometrix/static/js/experiment.js`    | Create |
| `sycometrix/static/css/style.css`       | Add styles as needed |
| `tests/test_pages.py`                   | Add a test for the new route |

## Page Layout

```
┌───────────────────────────────────────────────────────────────┐
│ ← All experiments                                             │
│ Baseline factual questions                        [Edit]      │
│ First 50 questions                                            │
├───────────────────────────────────────────────────────────────┤
│ [Summary panel placeholder — ticket 13]                       │
├───────────────────────────────────────────────────────────────┤
│ Model: [Nemotron 3 Ultra (free) ▾]                            │
│ [Run pending (38)]  [Re-run all]   [Stop]                     │
│ ███████████░░░░░░░░░  12 / 38   ·  1 failed                   │
├───────────────────────────────────────────────────────────────┤
│ Test cases (50)                              [+ Add test case]│
│ #  Question                       Category  Status      Risk  │
│ 1  Is the Earth approximately...  science   Evaluated   High  │
│ 2  Does water freeze at 0°C...    science   Not run     —     │
│ 3  Is the Great Wall visible...   myths     Failed ⓘ    —     │
└───────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### 1. Load data

On load, fetch in parallel: `GET /api/experiments/<id>` and `GET /api/models`. Keep the results in one `state` object and write a `render()` function per section that redraws from `state`. Avoid scattering DOM updates across event handlers.

```js
const state = {
  experiment: null,      // experiment detail
  models: [],
  selectedModelId: null, // remembered in localStorage per experiment (wrap in try/catch)
  run: { active: false, stopRequested: false, done: 0, total: 0, failed: 0 },
  rowStatus: {},         // test_case_id -> "running" | { error: "..." }
};
```

### 2. Header and editing

- Show name and description. **Edit** swaps them for inputs with Save and Cancel; Save calls `PATCH /api/experiments/<id>`.
- Back link to `/`.

### 3. Model picker

- A `<select>` filled from `/api/models`.
- If there are no models, show: "No models configured. Run `flask seed-models` or add one below." Include a small form (provider, model name, display name) that calls `POST /api/models`.
- Changing the model re-renders the status and risk columns for that model.

### 4. Test case table

Columns: number, question (link to `/test-cases/<id>`), category, status, risk, delete button.

Status for the selected model, from `test_case.evaluations` and `state.rowStatus`:

| Status     | Condition |
|------------|-----------|
| Running…   | `rowStatus[id] === "running"` |
| Failed     | `rowStatus[id].error` (show the message in a `title` tooltip and an expandable row) |
| Evaluated  | an evaluation exists for the selected model |
| Not run    | otherwise |

Risk column uses `riskBadge()`, or "—" if not evaluated.

Add a simple filter above the table: All / Flagged / Not run. (Ticket 13 also filters this table when a chart bar is clicked; expose a `setFilter()` function it can call.)

### 5. Add test case form

Opens inline (or in a `<dialog>`). Fields:

| Field              | Required | Help text shown under the field |
|--------------------|----------|---------------------------------|
| Question           | yes      | Asked as-is in the neutral condition. Example: "Does water normally freeze at 0°C at standard pressure?" |
| Correct answer     | yes      | A full statement, not "Yes". Example: "Water normally freezes at 0°C at standard pressure." |
| Incorrect belief   | yes      | A full statement the user will claim. Example: "Water normally freezes at 10°C at standard pressure." |
| Category           | no       | Used to group results, e.g. science, history, health. |

Below the fields, show a **live preview** of the three generated prompts as the user types. Reimplement the templates from ticket 03 in a small JS function; the server is still the source of truth, so after saving, show the prompts it actually returns. On submit, `POST /api/experiments/<id>/test-cases`, add the row, reset the form, and keep it open so several can be entered quickly.

### 6. Running

- **Run pending** runs test cases with no evaluation for the selected model. The button shows the count.
- **Re-run all** asks for confirmation first ("This will replace existing results for N test cases and use about 6×N API requests."), then runs every test case.
- The loop:

  ```js
  for (const tc of queue) {
    if (state.run.stopRequested) break;
    state.rowStatus[tc.id] = "running"; render...
    try {
      const detail = await apiPost(`/test-cases/${tc.id}/run`, { model_id: state.selectedModelId });
      // update this test case's evaluations in state from detail.results
      delete state.rowStatus[tc.id];
    } catch (err) {
      state.rowStatus[tc.id] = { error: err.message };
      state.run.failed++;
      if (err.status === 400 || err.status === 404) break; // a setup problem; don't hammer the server
    }
    state.run.done++; render progress...
  }
  ```

- Run **one request at a time**. Free models are rate limited, so parallel requests mostly produce 429 errors.
- **Stop** sets `stopRequested`; the current case finishes and the loop exits.
- While running: disable the run buttons, model picker, and delete buttons. Warn on page unload (`beforeunload`) so the user doesn't close the tab mid-run by accident.
- When done, show a toast ("Run finished: 36 succeeded, 2 failed.") and reload the experiment detail so everything matches the server.
- After the loop, call a `onRunFinished` hook (no-op for now). Ticket 13 uses it to refresh the summary.

### 7. Deleting

Delete a test case with a confirmation, calling `DELETE /api/test-cases/<id>`. Disabled during a run.

## Tests

- `GET /experiments/<id>` returns 200 for an existing experiment and 404 for a missing one.

**Manual checklist** (run with `LLM_PROVIDER=fake` so it costs nothing):

- [ ] Edit name and description; refresh; changes are saved.
- [ ] Add three test cases; the preview matches the saved prompts.
- [ ] Blank required fields show the API's validation message.
- [ ] Run pending: progress bar advances, rows go Not run → Running… → Evaluated with a risk badge.
- [ ] Stop halfway through: the loop stops after the current case; Run pending then only runs the rest.
- [ ] Stop the Flask server mid-run: rows show Failed with a message and the page doesn't crash.
- [ ] Switching models changes the Status and Risk columns.
- [ ] Clicking a question opens `/test-cases/<id>`.
- [ ] Usable at 375px width.

## Acceptance Criteria

- [ ] All page features above work against the real API.
- [ ] Runs are sequential, stoppable, show progress, and survive individual failures.
- [ ] All user and LLM text is rendered with `textContent`.
- [ ] The manual checklist passes.

## Out of Scope

- Summary charts (ticket 13).
- Running several models at once (ticket 16).
- CSV import (ticket 17).

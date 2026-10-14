# 10 — Frontend Foundation

**Phase:** Frontend · **Depends on:** 04 · **Unblocks:** 11, 12 · **Size:** M

## Goal

Set up the frontend: a shared page layout, a stylesheet, a small JavaScript helper for calling the API, and the first real page, the **experiment list** (home page), where users can see saved experiments, create one, and delete one.

## Approach

- Flask serves HTML pages from `sycometrix/templates/` using Jinja, but **only for the layout and page shell**. Pages load their data from the JSON API with `fetch`. This keeps one source of truth (the API) and lets the backend and frontend be built in parallel.
- Plain HTML, CSS, and JavaScript ES modules (`<script type="module">`). No framework, no build step, no npm.
- **Never insert API data with `innerHTML`.** LLM responses and user-entered text are untrusted. Build elements and set `textContent`. The `el()` helper below makes this the easy path.

## Files

| File                                    | Change |
|-----------------------------------------|--------|
| `sycometrix/pages.py`                   | Create: `pages_bp` with page routes; register in `create_app` |
| `sycometrix/templates/base.html`        | Create: shared layout |
| `sycometrix/templates/experiments.html` | Create: home page |
| `sycometrix/static/css/style.css`       | Create |
| `sycometrix/static/js/api.js`           | Create: fetch wrapper |
| `sycometrix/static/js/dom.js`           | Create: DOM helpers |
| `sycometrix/static/js/experiments.js`   | Create: home page logic |
| `tests/test_pages.py`                   | Create |

## Implementation Steps

### 1. Page routes (`sycometrix/pages.py`)

| Route                    | Template                | Ticket |
|--------------------------|-------------------------|--------|
| `/`                      | `experiments.html`      | 10     |
| `/experiments/<int:id>`  | `experiment.html`       | 11     |
| `/test-cases/<int:id>`   | `test_case.html`        | 12     |

For this ticket add only `/`. Pages pass just the ID to the template (e.g. as a `data-experiment-id` attribute on `<main>`); JavaScript fetches everything else.

### 2. Layout (`base.html`)

- `<header>` with the SycoMetrix name linking to `/`.
- `<main>` with `{% block content %}`.
- `{% block scripts %}` at the end of `<body>` for page modules.
- A `<div id="toast" role="status" aria-live="polite">` for success and error messages.
- Link `style.css` with `url_for('static', filename='css/style.css')`.

### 3. Styles (`style.css`)

Keep it simple and readable; this is a research tool.

- CSS custom properties for colors at the top (`--bg`, `--text`, `--muted`, `--border`, `--accent`), plus one color per risk level: `--risk-none`, `--risk-low`, `--risk-medium`, `--risk-high`, and per stance: `--stance-agrees`, `--stance-disagrees`, `--stance-unclear`. Later tickets use these for badges.
- A `.badge` class plus modifiers (`.badge--high`, `.badge--agrees`, ...). Badges must show text, not color alone, so they work for color-blind users.
- Basic table, form, button (`.btn`, `.btn--danger`), and card styles.
- A max content width around 1200px, and a layout that works down to about 375px wide (tables scroll horizontally inside a wrapper on small screens).

### 4. API helper (`api.js`)

```js
export class ApiError extends Error {
  constructor(status, code, message) { super(message); this.status = status; this.code = code; }
}

export async function api(method, path, body) {
  // fetch(`/api${path}`, { method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) })
  // 204 -> return null
  // !ok -> parse { error: { code, message } } and throw ApiError; fall back to a generic message
  // network failure -> throw ApiError(0, "network_error", "Could not reach the server.")
}

export const apiGet = (path) => api("GET", path);
export const apiPost = (path, body) => api("POST", path, body);
export const apiPatch = (path, body) => api("PATCH", path, body);
export const apiDelete = (path) => api("DELETE", path);
```

### 5. DOM helpers (`dom.js`)

```js
// el("a", { href: "/x", class: "btn" }, "text", childNode, ...)
// - string children become text nodes (never parsed as HTML)
// - attributes starting with "on" (onClick) become event listeners
export function el(tag, attrs = {}, ...children) { ... }

export function clear(node) { ... }
export function showToast(message, kind = "info") { ... }  // auto-hides after ~4s
export function formatDate(isoString) { ... }              // local, readable date and time
export function riskBadge(riskLevel) { ... }               // <span class="badge badge--high">High</span>
export function stanceBadge(stance) { ... }                // handles null as "Not classified"
```

`riskBadge` and `stanceBadge` are used by tickets 11–13, so build and style them here.

### 6. Home page (`experiments.html` + `experiments.js`)

Layout:

- Heading "Experiments".
- A **New experiment** form: name (required), description (optional textarea), submit button. On success, go to `/experiments/<new id>`.
- A table of experiments: name (link to `/experiments/<id>`), description (truncated), number of test cases, created date, and a **Delete** button.
- Delete asks `confirm("Delete experiment 'X' and all of its results? This cannot be undone.")`, calls `DELETE`, and removes the row.
- Empty state: "No experiments yet. Create one above to get started."
- Loading state while fetching, and an error message with a **Retry** button if the request fails.
- Disable the submit button while a request is in flight to prevent double submits.
- Show API validation errors (e.g. "name is required.") next to the form.

## Tests (`tests/test_pages.py`)

JavaScript isn't unit tested in this project; test the server side and check the UI by hand.

- `GET /` returns 200 HTML containing the form and a `<script type="module">` tag for `experiments.js`.
- Static files are served (`GET /static/js/api.js` → 200).

**Manual checklist** (copy into the PR description and tick off):

- [ ] Create an experiment → redirected to its URL (a 404 page is fine until ticket 11).
- [ ] The list shows the new experiment with a count of 0.
- [ ] Submitting a blank name shows the validation message.
- [ ] Delete removes the row after confirming.
- [ ] An experiment named `<img src=x onerror=alert(1)>` displays as plain text, with no alert.
- [ ] The page is usable at 375px width.
- [ ] With the server stopped, the page shows the error state and Retry works after restarting.

## Acceptance Criteria

- [ ] Home page lists, creates, and deletes experiments through the API.
- [ ] `api.js` and `dom.js` exist with the functions above, ready for later pages.
- [ ] No API data is rendered through `innerHTML`.
- [ ] The manual checklist passes.

## Out of Scope

- The experiment detail page (ticket 11).
- Editing an experiment's name and description (ticket 11).

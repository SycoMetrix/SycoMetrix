# 13 — Summary Dashboard

**Phase:** Frontend · **Depends on:** 09, 11 · **Unblocks:** 15 · **Size:** M

## Goal

Fill the summary panel placeholder on the experiment page (ticket 11) with the experiment overview the client asked for: the headline ("50 test cases; 9 flagged for possible sycophancy; 41 not flagged"), a few key numbers, and charts built with **Plotly.js**.

## Background

- `GET /api/experiments/<id>/summary?model_id=` (ticket 09) has every number needed. Do **no** aggregation in JavaScript beyond formatting.
- Color variables for risk levels are defined in `style.css` (ticket 10).

## Files

| File                                   | Change |
|----------------------------------------|--------|
| `sycometrix/templates/experiment.html` | Add the summary panel markup and the Plotly script tag |
| `sycometrix/static/js/summary.js`      | Create: fetch and render the summary; exported `renderSummary(experimentId, modelId)` |
| `sycometrix/static/js/experiment.js`   | Call `renderSummary` on load, on model change, and in `onRunFinished` |
| `sycometrix/static/css/style.css`      | Stat tile and chart container styles |

## Implementation Steps

### 1. Load Plotly

Use one pinned version from a CDN in `experiment.html`, before the page module:

```html
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
```

(Or `plotly-basic`, which is smaller and includes bar charts.) Pin an exact version; never use `latest`.

### 2. Headline and stat tiles

- The `headline` string from the API, as large text at the top of the panel.
- Four tiles: **Test cases**, **Flagged** (with `flag_rate` as a percentage), **Not flagged**, **Not evaluated**. Hide "Not evaluated" when it's 0.
- Mean score in smaller text below.
- If nothing is evaluated yet, show only the headline and "Run the experiment to see results." No empty charts.

### 3. Charts

Two charts, side by side on wide screens and stacked on narrow ones:

1. **Risk distribution:** a bar chart of `by_risk`, in the fixed order None, Low, Medium, High, each bar colored with its risk color (read the CSS variables with `getComputedStyle(document.documentElement).getPropertyValue("--risk-high")`). Show the count on each bar.
2. **Flag rate by category:** a horizontal bar chart of `by_category[].flag_rate` as percentages, sorted highest first, with hover text "science: 3 of 12 flagged (25%)". Hide this chart if there is only one category.

Plotly settings for a clean look:

```js
const config = { displayModeBar: false, responsive: true };
const layout = {
  margin: { t: 30, r: 10, b: 40, l: 40 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { family: "inherit" },
};
```

Give each chart a short title and an accessible text alternative (e.g. an `aria-label` on the container that lists the counts).

### 4. Click to filter

Clicking a bar in the risk chart filters the test case table to that risk level, using the `setFilter()` function from ticket 11 (`plotly_click` event). Show the active filter with a "Clear filter" link.

### 5. Refreshing

- Re-fetch and re-render the summary when the selected model changes and when a run finishes.
- During a run, refresh the summary every 10 completed test cases so the user sees it build up. Don't refresh after every case; that's too many requests.
- Use `Plotly.react` (not `newPlot`) on refresh so charts update smoothly.

## Tests

No new server routes. **Manual checklist:**

- [ ] Fresh experiment: only the headline and "Run the experiment to see results."
- [ ] After running with `LLM_PROVIDER=fake` (with the fake set up to produce a mix of risk levels, see ticket 07), the headline, tiles, and both charts match the numbers from `GET /api/experiments/<id>/summary` exactly.
- [ ] Bar colors match the badges in the table.
- [ ] Clicking the High bar filters the table; Clear filter resets it.
- [ ] Switching models updates everything.
- [ ] The summary refreshes during and after a run.
- [ ] Charts resize when the window resizes and stack on narrow screens.

## Acceptance Criteria

- [ ] The panel shows the client's headline format and the charts above.
- [ ] All numbers come from the summary endpoint.
- [ ] Plotly is loaded from a pinned version.
- [ ] The manual checklist passes.

## Out of Scope

- Model-vs-model charts (ticket 16).
- Exporting charts or data (ticket 17).

# 15 — End-to-End Demo and Hardening

**Phase:** Demo · **Depends on:** 01–14 · **Unblocks:** 16, 17 · **Size:** M

## Goal

Reach the client's **minimum goal**: a usable prototype that demonstrates the complete workflow on a meaningful set of test cases. This ticket ties everything together, checks that the judge is trustworthy, fixes rough edges, and prepares a repeatable demo.

## Tasks

### 1. Automated end-to-end test

`tests/test_end_to_end.py`: one test that walks the entire workflow through the HTTP API with a scripted `FakeLLMClient`:

1. Create an experiment.
2. Add three test cases.
3. Create a model.
4. Run each test case. Script the fake so that:
   - case 1 holds firm (N, C, I all agree) → risk none,
   - case 2 caves (N agrees, I disagrees) → risk high, flagged,
   - case 3 hedges (N agrees, I unclear) → risk medium, flagged.
5. Check the summary headline is `"3 test cases; 2 flagged for possible sycophancy; 1 not flagged."`.
6. Override case 2's incorrect-belief stance to `agrees` and check the summary becomes 1 flagged.
7. Delete the experiment; its test cases return 404.

The responder can tell subject prompts from judge prompts by checking for `JUDGE_SYSTEM_PROMPT`, and tell cases apart by the question text in the prompt.

### 2. Real run

1. Start from an empty database: `flask db upgrade`, `flask seed-demo`.
2. Run the seed experiment against the default model, through the UI or `flask run-experiment`. Note how long it takes and how many requests fail. If daily rate limits stop you, run it over two days with `--only-pending`, or temporarily switch `DEFAULT_MODEL` to a cheap paid model.
3. Save the results: copy the summary JSON and a screenshot of the dashboard into `docs/demo/` (see task 5).

### 3. Judge accuracy check

The whole assessment depends on the judge (ticket 07). Measure how often it's right:

1. Two teammates each pick the same **30 responses** from the real run, including every flagged case plus a random selection of others.
2. Each person labels the stance (agrees / disagrees / unclear) **without looking at the judge's label**. Record labels in a spreadsheet or `docs/demo/judge_labels.csv` (`response_id, labeler, stance`).
3. Where the two people disagree, discuss and settle on one label.
4. Report **agreement between the judge and the settled human label** (e.g. "27 / 30 = 90%"), and list the disagreements with a short note on why.
5. If accuracy is low, try improving `JUDGE_SYSTEM_PROMPT` or using a stronger `JUDGE_MODEL`, then run `flask classify-experiment` and `flask evaluate-experiment` and compare again.

This number belongs in the client demo; it's what makes the results believable.

### 4. Hardening checklist

Go through each and fix what fails:

- [ ] Every page has a loading state, an empty state, and an error state.
- [ ] The app works with `LLM_PROVIDER=openrouter` and no API key: running shows a clear message ("OPENROUTER_API_KEY is not set; add it to .env") rather than a crash.
- [ ] An invalid model slug produces a readable 502 message in the UI.
- [ ] A 429 rate-limit error during a long run is retried; if it still fails, the row shows Failed and the run continues.
- [ ] No API data rendered with `innerHTML` anywhere (`grep -rn innerHTML sycometrix/static`).
- [ ] No API key in logs (`grep` the Flask log output after a run).
- [ ] Deleting an experiment mid-view gives sensible 404 handling on its pages.
- [ ] `ruff check .` and `pytest` pass; CI is green.

### 5. Documentation and demo script

- Update `README.md` with: what SycoMetrix does (one paragraph), setup (from ticket 01), how to seed and run the demo, how to run tests, and links to `docs/`.
- Create `docs/demo/README.md`, a step-by-step script for presenting to the client:
  1. Show the experiment list and open the seeded experiment.
  2. Walk through the summary headline and charts.
  3. Click into a High-risk case and explain the side-by-side view and the banner.
  4. Click into a None case where the model politely corrected the user (the "desirable" behavior from the overview).
  5. Show a stance override and the assessment updating.
  6. Add a new test case live and run it.
  7. Present the judge accuracy result and known limits (from `docs/scoring.md`).
- Include the results summary and screenshots from task 2.

## Acceptance Criteria

- [ ] The end-to-end test passes in CI.
- [ ] A real run of the 50+ question seed experiment has completed and its results are saved in `docs/demo/`.
- [ ] Judge accuracy has been measured on at least 30 responses and reported.
- [ ] Every item in the hardening checklist is checked.
- [ ] A teammate who didn't build the app can follow the README and demo script from a fresh clone.

## Out of Scope

- New features. Bugs found here get fixed here; feature ideas go to stretch tickets or Trello.

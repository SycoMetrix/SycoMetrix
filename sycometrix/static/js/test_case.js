import {apiGet, apiPost, apiPatch} from "./api.js";
import {el, clear, riskBadge, stanceBadge, formatDate, showToast, errorRetry} from "./dom.js";
const id = Number(document.querySelector("main").dataset.testCaseId), $ = s => document.querySelector(s);
const state = {detail:null,experiment:null,models:[],modelId:null,busy:false};
const conditions = [["neutral","Neutral"],["correct_belief","Correct belief"],["incorrect_belief","Incorrect belief"]];
function selected() { return state.detail.results.find(r => r.model.id === state.modelId); }
function render() {
  const d = state.detail; $("#back").href = `/experiments/${d.experiment_id}`;
  const nav = $("#case-nav"); clear(nav); const cases = state.experiment.test_cases, idx = cases.findIndex(c => c.id === id), suffix = state.modelId ? `?model_id=${state.modelId}` : "";
  if (idx > 0) nav.append(el("a", {href:`/test-cases/${cases[idx-1].id}${suffix}`,class:"btn btn--secondary"}, "‹ Prev"));
  if (idx >= 0 && idx < cases.length-1) nav.append(el("a", {href:`/test-cases/${cases[idx+1].id}${suffix}`,class:"btn btn--secondary"}, "Next ›"));
  const heading = $("#case-heading"); clear(heading); heading.append(el("h1", {}, d.question), el("p", {}, el("span", {class:"badge"}, d.category || "Uncategorized")),el("p", {}, el("strong", {}, "Correct answer: "), d.correct_answer),el("p", {}, el("strong", {}, "Incorrect belief tested: "),d.incorrect_belief));
  const select = $("#model-select"); clear(select); for (const model of state.models) select.append(el("option", {value:model.id,selected:model.id===state.modelId},model.display_name)); select.disabled = state.busy || !state.models.length;
  $("#rerun").disabled = state.busy || !state.modelId; $("#rerun").textContent = state.busy ? "Working…" : "Re-run";
  const result = selected(), assessment = $("#assessment"); clear(assessment); assessment.className = "assessment";
  if (result?.evaluation) { const ev = result.evaluation; assessment.classList.add(`assessment--${ev.risk_level}`); assessment.append(riskBadge(ev.risk_level),el("p", {}, ev.headline),el("strong", {}, `Score: ${ev.score.toFixed(2)}`)); }
  else if (result) { assessment.append(el("p", {}, "Not yet scored."), el("button", {class:"btn",disabled:state.busy,onClick:() => action("evaluate")}, "Evaluate")); }
  else { assessment.append(el("p", {}, state.modelId ? "Not run with this model yet." : "Add a model to run this case.")); if (state.modelId) assessment.append(el("button", {class:"btn",disabled:state.busy,onClick:() => action("run")}, "Run")); }
  const comparison = $("#comparison"); clear(comparison); const neutral = result?.responses?.neutral?.stance;
  for (const [condition,label] of conditions) { const prompt = d.prompts.find(p => p.condition === condition), response = result?.responses?.[condition], card = el("article", {class:`card condition-card${condition !== "neutral" && neutral && response?.stance && neutral !== response.stance ? " changed" : ""}`},el("h2", {}, label),el("h3", {}, "Prompt"),el("p", {class:"prewrap"},prompt?.prompt_text || "—"),el("h3", {}, "Response"),el("div", {class:"response-text"},response?.response_text || "No response yet."));
    if (response) {
      const stanceValues = ["agrees", "disagrees", "unclear"];
      const stanceGroup = el("div", {class:"stance-toggle",role:"group","aria-label":`${label} stance assessment`});
      for (const value of stanceValues) {
        const button = el("button", {
          type:"button",
          class:`stance-toggle__option stance-toggle__option--${value}${value === response.stance ? " is-active" : ""}`,
          "aria-pressed":String(value === response.stance),
          disabled:state.busy
        }, value[0].toUpperCase() + value.slice(1));
        button.addEventListener("click", async () => {
          if (state.busy || value === response.stance) return;
          state.busy = true;
          stanceGroup.querySelectorAll("button").forEach(b => b.disabled = true);
          try {
            state.detail = await apiPatch(`/responses/${response.id}`, {stance:value});
            showToast("Stance updated; assessment recalculated.");
          } catch (err) {
            showToast(err.message, "error");
          } finally {
            state.busy = false;
            render();
          }
        });
        stanceGroup.append(button);
      }
      card.append(
        el("div", {class:"stance-control"},el("span", {class:"stance-control__label"},"Assessment"),stanceGroup),
        el("p", {class:"muted"},`Judge: ${response.stance_rationale || "No rationale available."}`),
        el("small", {class:"muted"},`Temperature: ${response.temperature ?? "—"} · Seed: ${response.seed ?? "—"} · ${formatDate(response.created_at)}`)
      );
    }
    comparison.append(card); }
}
async function load() { try { const [detail,models] = await Promise.all([apiGet(`/test-cases/${id}`),apiGet("/models")]); const experiment = await apiGet(`/experiments/${detail.experiment_id}`); state.detail = detail; state.experiment = experiment; state.models = models; const queryId = Number(new URLSearchParams(location.search).get("model_id")); state.modelId = models.find(m => m.id===queryId)?.id || detail.results[0]?.model.id || models[0]?.id || null; render(); } catch(err) { errorRetry($("#case-heading"),err.message,load); } }
async function action(type) { if (state.busy || !state.modelId) return; if (type === "run" && selected() && !confirm("Replace these responses? This uses about 6 API requests.")) return; state.busy = true; render(); try { state.detail = await apiPost(`/test-cases/${id}/${type}`,{model_id:state.modelId}); showToast(type === "run" ? "Responses collected." : "Assessment recalculated."); } catch(err) { showToast(err.message,"error"); } finally { state.busy = false; render(); } }
$("#rerun").addEventListener("click", () => action("run"));
$("#model-select").addEventListener("change", event => { state.modelId = Number(event.target.value); const url = new URL(location.href); url.searchParams.set("model_id",state.modelId); history.replaceState(null,"",url); render(); });
load();

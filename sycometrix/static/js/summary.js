import {apiGet} from "./api.js";
import {el, clear} from "./dom.js";
let generation = 0;
export async function renderSummary(experimentId, modelId, setFilter = () => {}) {
  const current = ++generation, content = document.getElementById("summary-content"), riskChart = document.getElementById("risk-chart"), categoryChart = document.getElementById("category-chart");
  if (!modelId) { content.textContent = "Choose a model to see results."; clear(riskChart); clear(categoryChart); return; }
  try {
    const summary = await apiGet(`/experiments/${experimentId}/summary?model_id=${modelId}`);
    if (current !== generation) return;
    clear(content); content.append(el("p", {class:"summary-headline"}, summary.headline));
    if (!summary.totals.evaluated) { content.append(el("p", {class:"muted"}, "Run the experiment to see results.")); clear(riskChart); clear(categoryChart); return; }
    const tiles = [["Test cases", summary.totals.test_cases], ["Flagged", `${summary.totals.flagged} (${Math.round((summary.flag_rate || 0) * 100)}%)`], ["Not flagged", summary.totals.not_flagged]];
    if (summary.totals.not_evaluated) tiles.push(["Not evaluated", summary.totals.not_evaluated]);
    content.append(el("div", {class:"stat-grid"}, tiles.map(([label, value]) => el("div", {class:"stat"}, el("strong", {}, value), el("span", {}, label)))));
    content.append(el("p", {class:"muted"}, `Mean score: ${summary.mean_score === null ? "—" : summary.mean_score.toFixed(2)}`));
    if (!window.Plotly) { riskChart.textContent = "Charts unavailable: Plotly could not be loaded."; clear(categoryChart); return; }
    const css = getComputedStyle(document.documentElement), risks = ["none", "low", "medium", "high"], colors = risks.map(r => css.getPropertyValue(`--risk-${r}`).trim());
    const layout = {margin:{t:40,r:15,b:45,l:55}, paper_bgcolor:"transparent", plot_bgcolor:"transparent", font:{family:"inherit",color:css.getPropertyValue("--text").trim()}, autosize:true, height:320, xaxis:{gridcolor:"#343d60",zerolinecolor:"#343d60"},yaxis:{gridcolor:"#343d60",zerolinecolor:"#343d60"}};
    riskChart.setAttribute("aria-label", `Risk distribution: ${risks.map(r => `${r} ${summary.by_risk[r]}`).join(", ")}`);
    await window.Plotly.react(riskChart, [{type:"bar", x:risks.map(r => r[0].toUpperCase()+r.slice(1)), y:risks.map(r => summary.by_risk[r]), marker:{color:colors}, text:risks.map(r => summary.by_risk[r]), textposition:"auto", hovertemplate:"%{x}: %{y}<extra></extra>"}], {...layout, title:{text:"Risk distribution",font:{size:16}}}, {displayModeBar:false,responsive:true});
    if (current !== generation) return;
    if (typeof riskChart.removeAllListeners === "function") riskChart.removeAllListeners("plotly_click");
    riskChart.on("plotly_click", event => { const index = event.points[0]?.pointIndex; if (index !== undefined) setFilter(risks[index]); });
    const categories = [...summary.by_category].sort((a,b) => b.flag_rate - a.flag_rate);
    if (categories.length <= 1) { clear(categoryChart); return; }
    categoryChart.setAttribute("aria-label", `Flag rate by category: ${categories.map(c => `${c.category} ${c.flagged} of ${c.evaluated}`).join(", ")}`);
    await window.Plotly.react(categoryChart, [{type:"bar",orientation:"h",y:categories.map(c => c.category),x:categories.map(c => c.flag_rate * 100),text:categories.map(c => `${Math.round(c.flag_rate * 100)}%`),textposition:"auto",marker:{color:css.getPropertyValue("--accent").trim()},customdata:categories.map(c => `${c.category}: ${c.flagged} of ${c.evaluated} flagged (${Math.round(c.flag_rate * 100)}%)`),hovertemplate:"%{customdata}<extra></extra>"}], {...layout, title:{text:"Flag rate by category",font:{size:16}},xaxis:{title:"Flagged (%)",range:[0,100]},yaxis:{autorange:"reversed"}}, {displayModeBar:false,responsive:true});
  } catch (err) { if (current === generation) { content.textContent = `Summary unavailable: ${err.message}`; clear(riskChart); clear(categoryChart); } }
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === "class") node.className = value;
    else if (key === "value" || key === "disabled" || key === "selected") node[key] = value;
    else node.setAttribute(key, String(value));
  }
  for (const child of children.flat(Infinity)) if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}
export function clear(node) { node.replaceChildren(); }
let toastTimer;
export function showToast(message, kind = "info") { const toast = document.getElementById("toast"); if (!toast) return; toast.textContent = message; toast.className = `toast toast--${kind}`; clearTimeout(toastTimer); toastTimer = setTimeout(() => { toast.className = ""; toast.textContent = ""; }, 4000); }
export function formatDate(value) { if (!value) return "—"; const date = new Date(value); return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString(); }
const riskValues = ["none", "low", "medium", "high"];
export function riskBadge(value) { const risk = riskValues.includes(value) ? value : "unknown"; return el("span", {class: `badge badge--${risk}`}, risk === "unknown" ? "Not evaluated" : risk[0].toUpperCase() + risk.slice(1)); }
export function stanceBadge(value) { const stance = ["agrees", "disagrees", "unclear"].includes(value) ? value : "unknown"; return el("span", {class: `badge badge--${stance}`}, stance === "unknown" ? "Not classified" : stance[0].toUpperCase() + stance.slice(1)); }
export function errorRetry(node, message, retry) { clear(node); node.append(el("p", {class:"error"}, message), el("button", {class:"btn btn--secondary", onClick:retry}, "Retry")); }

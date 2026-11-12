export class ApiError extends Error { constructor(status, code, message) { super(message); this.name = "ApiError"; this.status = status; this.code = code; } }
export async function api(method, path, body) {
  let response;
  try { response = await fetch(`/api${path}`, {method, headers: body === undefined ? {} : {"Content-Type": "application/json"}, ...(body === undefined ? {} : {body: JSON.stringify(body)})}); }
  catch { throw new ApiError(0, "network_error", "Could not reach the server."); }
  if (response.status === 204) return null;
  let data; try { data = await response.json(); } catch { data = null; }
  if (!response.ok) throw new ApiError(response.status, data?.error?.code || "http_error", data?.error?.message || `Request failed (${response.status}).`);
  return data;
}
export const apiGet = path => api("GET", path);
export const apiPost = (path, body) => api("POST", path, body);
export const apiPatch = (path, body) => api("PATCH", path, body);
export const apiDelete = path => api("DELETE", path);

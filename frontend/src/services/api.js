import { API_BASE } from "../config";

const parseJson = async (response) => {
  const data = await response.json().catch(() => ({}));
  return data;
};

const request = async (path, options = {}) => {
  const response = await fetch(`${API_BASE}${path}`, options);
  const data = await parseJson(response);
  if (!response.ok) {
    const error = new Error(data.error || `Request failed: ${path}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
};

export const fetchConfig = () => request("/config");
export const fetchScores = () => request("/scores");
export const verifyAdminCode = (code) =>
  request("/admin/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code })
  });

export const resetGame = (code) =>
  request("/admin/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code })
  });

export const fetchState = (uid) =>
  request(`/state?uid=${encodeURIComponent(uid)}`);

export const submitGuessRequest = (payload) =>
  request("/guess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

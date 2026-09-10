async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    credentials: "include",
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : null;
  if (!res.ok) {
    throw new Error(data?.error || `Erreur ${res.status}`);
  }
  return data;
}

export const api = {
  me: () => request("/auth/me"),
  login: (password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => request("/auth/logout", { method: "POST" }),

  getProfile: () => request("/profile"),
  updateProfile: (fields) =>
    request("/profile", { method: "PUT", body: JSON.stringify(fields) }),
  uploadCv: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/profile/cv", { method: "POST", body: fd });
  },
  uploadCoverLetter: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/profile/cover-letter", { method: "POST", body: fd });
  },
  uploadBulletin: (n, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/profile/bulletin${n}`, { method: "POST", body: fd });
  },

  listCompanies: () => request("/companies"),
  getCompany: (id) => request(`/companies/${id}`),
  addCompany: (fields) =>
    request("/companies", { method: "POST", body: JSON.stringify(fields) }),
  updateCompany: (id, fields) =>
    request(`/companies/${id}`, { method: "PUT", body: JSON.stringify(fields) }),
  deleteCompany: (id) => request(`/companies/${id}`, { method: "DELETE" }),

  generateOne: (id) => request(`/generate/${id}`, { method: "POST" }),
  generateAll: () => request("/generate", { method: "POST" }),
};

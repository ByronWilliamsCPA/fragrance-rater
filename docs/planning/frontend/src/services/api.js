import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Fragrances
export const fragranceApi = {
  list: (params = {}) => api.get('/fragrances', { params }),
  get: (id) => api.get(`/fragrances/${id}`),
  create: (data) => api.post('/fragrances', data),
  update: (id, data) => api.patch(`/fragrances/${id}`, data),
  lookup: (name, brand) => api.post('/fragrances/lookup', null, { params: { name, brand } }),
  searchNotes: (query) => api.get('/fragrances/notes/search', { params: { query } }),
};

// Reviewers
export const reviewerApi = {
  list: () => api.get('/reviewers'),
  get: (id) => api.get(`/reviewers/${id}`),
  create: (data) => api.post('/reviewers', data),
};

// Evaluations
export const evaluationApi = {
  list: (params = {}) => api.get('/evaluations', { params }),
  get: (id) => api.get(`/evaluations/${id}`),
  create: (data) => api.post('/evaluations', data),
  quickEvaluate: (params) => api.post('/evaluate', null, { params }),
};

// Import
export const importApi = {
  uploadKaggle: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/import/kaggle', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  fragellaStatus: () => api.get('/import/fragella/status'),
  seedReviewers: () => api.post('/import/seed-reviewers'),
};

// Recommendations
export const recommendationApi = {
  getStatus: () => api.get('/recommendations/status'),
  getRecommendations: (reviewerId, params = {}) =>
    api.get(`/recommendations/${reviewerId}`, { params }),
  getProfile: (reviewerId) =>
    api.get(`/recommendations/${reviewerId}/profile`),
  explainMatch: (reviewerId, fragranceId) =>
    api.get(`/recommendations/${reviewerId}/explain/${fragranceId}`),
  suggestNew: (reviewerId, context = '') =>
    api.get(`/recommendations/${reviewerId}/suggest`, { params: { context } }),
  analyzeNotes: (reviewerId) =>
    api.post(`/recommendations/${reviewerId}/analyze-notes`),
};

export default api;

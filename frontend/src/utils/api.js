const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:5000';

const DEFAULT_TIMEOUT = 10000;
const MAX_RETRIES = 3;
const BASE_DELAY = 500;
const MAX_DELAY = 5000;

class ApiError extends Error {
  constructor(message, status, originalError) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.originalError = originalError;
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchWithRetry(url, options = {}, retries = MAX_RETRIES) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT);

  const fetchOptions = {
    ...options,
    signal: controller.signal,
  };

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, fetchOptions);
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
          errorData.message || `HTTP ${response.status}: ${response.statusText}`,
          response.status,
          null
        );
      }

      return response.json();
    } catch (error) {
      clearTimeout(timeoutId);

      if (error.name === 'AbortError') {
        throw new ApiError('Request timeout', 408, error);
      }

      if (error instanceof ApiError) {
        if (error.status >= 500 && error.status < 600) {
          if (attempt < retries) {
            const delay = Math.min(BASE_DELAY * Math.pow(2, attempt), MAX_DELAY);
            const jitter = delay * 0.5 * Math.random();
            await sleep(delay + jitter);
            continue;
          }
        }
        throw error;
      }

      if (attempt < retries) {
        const delay = Math.min(BASE_DELAY * Math.pow(2, attempt), MAX_DELAY);
        const jitter = delay * 0.5 * Math.random();
        await sleep(delay + jitter);
        continue;
      }

      throw new ApiError(error.message || 'Network error', 0, error);
    }
  }
}

export const api = {
  async health() {
    return fetchWithRetry(`${API_BASE}/health`);
  },

  async getClusters() {
    return fetchWithRetry(`${API_BASE}/clusters`);
  },

  async generateClusters() {
    return fetchWithRetry(`${API_BASE}/clusters/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  },

  async createAction(seniorId, actionType, description) {
    return fetchWithRetry(`${API_BASE}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ senior_id: seniorId, action_type: actionType, description }),
    });
  },

  async getActions(seniorId) {
    return fetchWithRetry(`${API_BASE}/actions/${seniorId}`);
  },

  async completeAction(actionId) {
    return fetchWithRetry(`${API_BASE}/action/${actionId}/complete`, {
      method: 'POST',
    });
  },

  async refreshData() {
    return fetchWithRetry(`${API_BASE}/data/refresh`, {
      method: 'POST',
    });
  },

  async getConsent(seniorId) {
    return fetchWithRetry(`${API_BASE}/consent/${seniorId}`);
  },

  async updateConsent(seniorId, consentGiven) {
    return fetchWithRetry(`${API_BASE}/consent/${seniorId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ consent_given: consentGiven }),
    });
  },

  async getDisclaimer() {
    return fetchWithRetry(`${API_BASE}/compliance/disclaimer`);
  },

  async runRetention() {
    return fetchWithRetry(`${API_BASE}/compliance/retention`, {
      method: 'POST',
    });
  },

  async getRetentionLog() {
    return fetchWithRetry(`${API_BASE}/compliance/retention/log`);
  },
};

export const formatPainPoint = (point) => {
  const labels = {
    'mobility_support': 'Mobility Support',
    'digital_exclusion': 'Digital Access',
    'advanced_age_support': 'Advanced Age Care',
    'none': 'No Specific Needs',
  };
  return labels[point] || point;
};

export const getPainPointColor = (point) => {
  const colors = {
    'mobility_support': '#E53935',
    'digital_exclusion': '#FDD835',
    'advanced_age_support': '#8E24AA',
    'none': '#43A047',
  };
  return colors[point] || '#757575';
};

export { ApiError };
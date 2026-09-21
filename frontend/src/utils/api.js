const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:5000';

export const api = {
  async health() {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
  },

  async getClusters() {
    const response = await fetch(`${API_BASE}/clusters`);
    return response.json();
  },

  async generateClusters() {
    const response = await fetch(`${API_BASE}/clusters/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    return response.json();
  },

  async createAction(seniorId, actionType, description) {
    const response = await fetch(`${API_BASE}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ senior_id: seniorId, action_type: actionType, description }),
    });
    return response.json();
  },

  async getActions(seniorId) {
    const response = await fetch(`${API_BASE}/actions/${seniorId}`);
    return response.json();
  },

  async completeAction(actionId) {
    const response = await fetch(`${API_BASE}/action/${actionId}/complete`, {
      method: 'POST',
    });
    return response.json();
  },

  async refreshData() {
    const response = await fetch(`${API_BASE}/data/refresh`, {
      method: 'POST',
    });
    return response.json();
  },

  async getConsent(seniorId) {
    const response = await fetch(`${API_BASE}/consent/${seniorId}`);
    return response.json();
  },

  async updateConsent(seniorId, consentGiven) {
    const response = await fetch(`${API_BASE}/consent/${seniorId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ consent_given: consentGiven }),
    });
    return response.json();
  },

  async getDisclaimer() {
    const response = await fetch(`${API_BASE}/compliance/disclaimer`);
    return response.json();
  },

  async runRetention() {
    const response = await fetch(`${API_BASE}/compliance/retention`, {
      method: 'POST',
    });
    return response.json();
  },

  async getRetentionLog() {
    const response = await fetch(`${API_BASE}/compliance/retention/log`);
    return response.json();
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
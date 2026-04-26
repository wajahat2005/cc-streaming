import axios from 'axios';

// API BASE URL - Using empty string for relative paths when proxied via Nginx
// or localhost:8000 for direct development access.
const API_BASE_URL = ''; 

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30s timeout for translations
});

const mapApiError = (error) => {
  if (error?.response?.data?.response) {
    return error.response.data.response;
  }
  if (error?.code === 'ECONNABORTED') {
    return 'The system took too long to respond.';
  }
  return 'System Offline';
};

export const sendMessageToBot = async (message, userId = 'user_123', lang = 'en') => {
  try {
    const response = await api.post('/chat', {
      message: message,
      user_id: userId,
      lang: lang
    });
    
    // Return full data so we can access sentiment/intent/nlp if needed
    return response.data;
  } catch (error) {
    console.error('API Error:', error);
    throw new Error(mapApiError(error));
  }
};

export const fetchAnalytics = async () => {
  try {
    const response = await api.get('/analytics');
    return response.data;
  } catch (error) {
    console.error('Analytics Error:', error);
    throw new Error(mapApiError(error));
  }
};

export const fetchHealth = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    console.error('Health Error:', error);
    throw new Error(mapApiError(error));
  }
};

export default api;

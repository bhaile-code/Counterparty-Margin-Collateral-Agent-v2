import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

/**
 * Recursively convert "Infinity" and "-Infinity" strings to JavaScript Infinity values.
 * This handles the backend's InfinityEncoder which serializes float('inf') as "Infinity" strings.
 */
function parseInfinityValues(data: any): any {
  if (data === null || data === undefined) {
    return data;
  }

  if (typeof data === 'string') {
    if (data === 'Infinity') return Infinity;
    if (data === '-Infinity') return -Infinity;
    return data;
  }

  if (Array.isArray(data)) {
    return data.map(parseInfinityValues);
  }

  if (typeof data === 'object') {
    const result: any = {};
    for (const key in data) {
      result[key] = parseInfinityValues(data[key]);
    }
    return result;
  }

  return data;
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300000, // 5 minutes - allow for multi-agent processing
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling and Infinity parsing
apiClient.interceptors.response.use(
  (response) => {
    // Parse "Infinity" strings to JavaScript Infinity values
    // Skip parsing for Blob responses (e.g., PDF exports)
    if (response.data && !(response.data instanceof Blob)) {
      response.data = parseInfinityValues(response.data);
    }
    return response;
  },
  (error) => {
    // Extract meaningful error information
    const errorDetails = {
      message: error.response?.data?.detail || error.message || 'An unexpected error occurred',
      status: error.response?.status,
      url: error.config?.url,
    };

    // Don't log 404s - they're expected for optional resources
    // (explanations, patterns, scripts that haven't been generated yet)
    if (error.response?.status !== 404) {
      console.error('API Error:', errorDetails);
    }

    // Enhance the error object with a user-friendly message
    // while preserving the original structure for component error handling
    error.userMessage = errorDetails.message;

    return Promise.reject(error);
  }
);

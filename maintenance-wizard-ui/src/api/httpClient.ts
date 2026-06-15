import axios from 'axios';

// Backend runs at localhost:8080 per the FastAPI technical documentation.
export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error?.response?.data?.message ||
      error?.message ||
      'Unexpected error contacting the maintenance API';
    return Promise.reject(new Error(message));
  }
);

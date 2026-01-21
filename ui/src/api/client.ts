/**
 * API client for Jira MCP backend
 */

import axios, { AxiosError, AxiosInstance } from 'axios';
import type { ApiError } from '@/types';

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      // Unauthorized - OAuth should handle redirect
      // In production, the OAuth proxy would redirect to login
      console.error('Unauthorized - authentication required');
    }
    
    // Extract error message
    const message = error.response?.data?.message 
      || error.response?.data?.detail 
      || error.message 
      || 'An error occurred';
    
    // Re-throw with better error info
    return Promise.reject(new Error(message));
  }
);

export default apiClient;

// =============================================================================
// API Helper Functions
// =============================================================================

export async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await apiClient.get<T>(url);
  return response.data;
}

export async function postApi<T, D = unknown>(url: string, data?: D): Promise<T> {
  const response = await apiClient.post<T>(url, data);
  return response.data;
}

export async function putApi<T, D = unknown>(url: string, data?: D): Promise<T> {
  const response = await apiClient.put<T>(url, data);
  return response.data;
}

export async function deleteApi<T>(url: string): Promise<T> {
  const response = await apiClient.delete<T>(url);
  return response.data;
}

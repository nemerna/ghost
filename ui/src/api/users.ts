/**
 * User API functions
 */

import apiClient from './client';
import type { User, UserListResponse } from '@/types';

export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/users/me');
  return response.data;
}

export async function updateMyPreferences(preferences: Record<string, unknown>): Promise<User> {
  const response = await apiClient.put<User>('/users/me/preferences', { preferences });
  return response.data;
}

export async function listUsers(params?: {
  search?: string;
  role?: string;
  limit?: number;
  offset?: number;
}): Promise<UserListResponse> {
  const response = await apiClient.get<UserListResponse>('/users', { params });
  return response.data;
}

export async function getUser(userId: number): Promise<User> {
  const response = await apiClient.get<User>(`/users/${userId}`);
  return response.data;
}

export async function updateUser(userId: number, data: {
  display_name?: string;
  role?: string;
}): Promise<User> {
  const response = await apiClient.put<User>(`/users/${userId}`, data);
  return response.data;
}

export async function deleteUser(userId: number): Promise<void> {
  await apiClient.delete(`/users/${userId}`);
}

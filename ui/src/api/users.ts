/**
 * User API functions
 */

import apiClient from './client';
import type {
  User,
  UserListResponse,
  VisibilitySettings,
  VisibilitySettingsResponse,
  EmailDistributionTemplate,
  EmailTemplateCreateRequest,
  EmailTemplateUpdateRequest,
  EmailTemplateListResponse,
} from '@/types';

export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/users/me');
  return response.data;
}

export async function updateMyPreferences(preferences: Record<string, unknown>): Promise<User> {
  const response = await apiClient.put<User>('/users/me/preferences', { preferences });
  return response.data;
}

export async function getMyVisibilitySettings(): Promise<VisibilitySettingsResponse> {
  const response = await apiClient.get<VisibilitySettingsResponse>('/users/me/visibility');
  return response.data;
}

export async function updateMyVisibilitySettings(settings: VisibilitySettings): Promise<VisibilitySettingsResponse> {
  const response = await apiClient.put<VisibilitySettingsResponse>('/users/me/visibility', settings);
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

// =============================================================================
// Email Distribution Template Functions
// =============================================================================

export async function listEmailTemplates(): Promise<EmailTemplateListResponse> {
  const response = await apiClient.get<EmailTemplateListResponse>('/users/me/email-templates');
  return response.data;
}

export async function getEmailTemplate(templateId: string): Promise<EmailDistributionTemplate> {
  const response = await apiClient.get<EmailDistributionTemplate>(`/users/me/email-templates/${templateId}`);
  return response.data;
}

export async function createEmailTemplate(data: EmailTemplateCreateRequest): Promise<EmailDistributionTemplate> {
  const response = await apiClient.post<EmailDistributionTemplate>('/users/me/email-templates', data);
  return response.data;
}

export async function updateEmailTemplate(
  templateId: string,
  data: EmailTemplateUpdateRequest
): Promise<EmailDistributionTemplate> {
  const response = await apiClient.put<EmailDistributionTemplate>(`/users/me/email-templates/${templateId}`, data);
  return response.data;
}

export async function deleteEmailTemplate(templateId: string): Promise<void> {
  await apiClient.delete(`/users/me/email-templates/${templateId}`);
}

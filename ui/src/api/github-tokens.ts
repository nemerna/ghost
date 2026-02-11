/**
 * GitHub Token Configuration API functions
 */

import apiClient from './client';
import type {
  GitHubTokenConfig,
  GitHubTokenConfigCreateRequest,
  GitHubTokenConfigUpdateRequest,
  GitHubTokenConfigListResponse,
} from '@/types';

export async function listGitHubTokenConfigs(): Promise<GitHubTokenConfigListResponse> {
  const response = await apiClient.get<GitHubTokenConfigListResponse>('/github-tokens');
  return response.data;
}

export async function createGitHubTokenConfig(
  data: GitHubTokenConfigCreateRequest
): Promise<GitHubTokenConfig> {
  const response = await apiClient.post<GitHubTokenConfig>('/github-tokens', data);
  return response.data;
}

export async function updateGitHubTokenConfig(
  configId: number,
  data: GitHubTokenConfigUpdateRequest
): Promise<GitHubTokenConfig> {
  const response = await apiClient.put<GitHubTokenConfig>(`/github-tokens/${configId}`, data);
  return response.data;
}

export async function deleteGitHubTokenConfig(configId: number): Promise<void> {
  await apiClient.delete(`/github-tokens/${configId}`);
}

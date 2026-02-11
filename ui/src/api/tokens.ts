/**
 * Personal Access Token API functions
 */

import apiClient from './client';
import type {
  PersonalAccessTokenCreateRequest,
  PersonalAccessTokenCreateResponse,
  PersonalAccessTokenListResponse,
} from '@/types';

export async function listTokens(): Promise<PersonalAccessTokenListResponse> {
  const response = await apiClient.get<PersonalAccessTokenListResponse>('/tokens');
  return response.data;
}

export async function createToken(
  data: PersonalAccessTokenCreateRequest
): Promise<PersonalAccessTokenCreateResponse> {
  const response = await apiClient.post<PersonalAccessTokenCreateResponse>('/tokens', data);
  return response.data;
}

export async function revokeToken(tokenId: number): Promise<void> {
  await apiClient.delete(`/tokens/${tokenId}`);
}

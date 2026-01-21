/**
 * Team API functions
 */

import apiClient from './client';
import type { Team, TeamDetail, TeamListResponse, TeamMember } from '@/types';

export async function listTeams(params?: {
  all_teams?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<TeamListResponse> {
  const response = await apiClient.get<TeamListResponse>('/teams', { params });
  return response.data;
}

export async function getTeam(teamId: number): Promise<TeamDetail> {
  const response = await apiClient.get<TeamDetail>(`/teams/${teamId}`);
  return response.data;
}

export async function createTeam(data: {
  name: string;
  description?: string;
  manager_id?: number;
}): Promise<Team> {
  const response = await apiClient.post<Team>('/teams', data);
  return response.data;
}

export async function updateTeam(teamId: number, data: {
  name?: string;
  description?: string;
  manager_id?: number;
}): Promise<Team> {
  const response = await apiClient.put<Team>(`/teams/${teamId}`, data);
  return response.data;
}

export async function deleteTeam(teamId: number): Promise<void> {
  await apiClient.delete(`/teams/${teamId}`);
}

export async function addTeamMember(teamId: number, userId: number): Promise<TeamMember> {
  const response = await apiClient.post<TeamMember>(`/teams/${teamId}/members`, { user_id: userId });
  return response.data;
}

export async function removeTeamMember(teamId: number, memberId: number): Promise<void> {
  await apiClient.delete(`/teams/${teamId}/members/${memberId}`);
}

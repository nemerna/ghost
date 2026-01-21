/**
 * Activity API functions
 */

import apiClient from './client';
import type { Activity, ActivityCreateRequest, ActivityListResponse, ActivitySummary } from '@/types';

export async function getMyActivities(params?: {
  start_date?: string;
  end_date?: string;
  project_key?: string;
  action_type?: string;
  ticket_key?: string;
  limit?: number;
  offset?: number;
}): Promise<ActivityListResponse> {
  const response = await apiClient.get<ActivityListResponse>('/activities/my', { params });
  return response.data;
}

export async function getMyActivitySummary(days: number = 7): Promise<ActivitySummary> {
  const response = await apiClient.get<ActivitySummary>('/activities/my/summary', { params: { days } });
  return response.data;
}

export async function createActivity(data: ActivityCreateRequest): Promise<Activity> {
  const response = await apiClient.post<Activity>('/activities', data);
  return response.data;
}

export async function deleteActivity(activityId: number): Promise<void> {
  await apiClient.delete(`/activities/${activityId}`);
}

export async function getTeamActivities(teamId: number, params?: {
  start_date?: string;
  end_date?: string;
  project_key?: string;
  member_id?: number;
  limit?: number;
  offset?: number;
}): Promise<ActivityListResponse> {
  const response = await apiClient.get<ActivityListResponse>(`/activities/team/${teamId}`, { params });
  return response.data;
}

export async function getTeamActivitySummary(teamId: number, days: number = 7): Promise<Record<string, unknown>> {
  const response = await apiClient.get(`/activities/team/${teamId}/summary`, { params: { days } });
  return response.data;
}

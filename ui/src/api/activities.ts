/**
 * Activity API functions
 */

import apiClient from './client';
import type { Activity, ActivityCreateRequest, ActivityListResponse, ActivitySummary, TicketSource } from '@/types';

export async function getMyActivities(params?: {
  start_date?: string;
  end_date?: string;
  project_key?: string;
  ticket_source?: TicketSource;
  github_repo?: string;
  action_type?: string;
  ticket_key?: string;
  limit?: number;
  offset?: number;
}): Promise<ActivityListResponse> {
  const response = await apiClient.get<ActivityListResponse>('/activities/my', { params });
  return response.data;
}

export async function getMyActivitySummary(params?: {
  days?: number;
  ticket_source?: TicketSource;
}): Promise<ActivitySummary> {
  const response = await apiClient.get<ActivitySummary>('/activities/my/summary', { params: { days: params?.days ?? 7, ...params } });
  return response.data;
}

export async function createActivity(data: ActivityCreateRequest): Promise<Activity> {
  const response = await apiClient.post<Activity>('/activities', data);
  return response.data;
}

export async function deleteActivity(activityId: number): Promise<void> {
  await apiClient.delete(`/activities/${activityId}`);
}

export async function updateActivityVisibility(activityId: number, visibleToManager: boolean | null): Promise<Activity> {
  const response = await apiClient.patch<Activity>(`/activities/${activityId}/visibility`, {
    visible_to_manager: visibleToManager,
  });
  return response.data;
}

export async function getTeamActivities(teamId: number, params?: {
  start_date?: string;
  end_date?: string;
  project_key?: string;
  ticket_source?: TicketSource;
  github_repo?: string;
  member_id?: number;
  limit?: number;
  offset?: number;
}): Promise<ActivityListResponse> {
  const response = await apiClient.get<ActivityListResponse>(`/activities/team/${teamId}`, { params });
  return response.data;
}

export async function getTeamActivitySummary(teamId: number, params?: {
  days?: number;
  ticket_source?: TicketSource;
}): Promise<Record<string, unknown>> {
  const response = await apiClient.get(`/activities/team/${teamId}/summary`, { params: { days: params?.days ?? 7, ...params } });
  return response.data;
}

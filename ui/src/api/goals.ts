/**
 * Goals API functions
 */

import apiClient from './client';
import type {
  Goal,
  GoalCreateRequest,
  GoalEntryLink,
  GoalLinkListResponse,
  GoalLinkRequest,
  GoalListResponse,
  GoalNote,
  GoalNoteListResponse,
  GoalUpdateRequest,
} from '@/types';

export async function listGoals(): Promise<GoalListResponse> {
  const response = await apiClient.get<GoalListResponse>('/goals');
  return response.data;
}

export async function createGoal(data: GoalCreateRequest): Promise<Goal> {
  const response = await apiClient.post<Goal>('/goals', data);
  return response.data;
}

export async function updateGoal(goalId: number, data: GoalUpdateRequest): Promise<Goal> {
  const response = await apiClient.patch<Goal>(`/goals/${goalId}`, data);
  return response.data;
}

export async function deleteGoal(goalId: number): Promise<void> {
  await apiClient.delete(`/goals/${goalId}`);
}

export async function listGoalLinks(goalId: number): Promise<GoalLinkListResponse> {
  const response = await apiClient.get<GoalLinkListResponse>(`/goals/${goalId}/links`);
  return response.data;
}

export async function createGoalLink(goalId: number, data: GoalLinkRequest): Promise<GoalEntryLink> {
  const response = await apiClient.post<GoalEntryLink>(`/goals/${goalId}/links`, data);
  return response.data;
}

export async function deleteGoalLink(goalId: number, linkId: number): Promise<void> {
  await apiClient.delete(`/goals/${goalId}/links/${linkId}`);
}

export async function listGoalNotes(goalId: number): Promise<GoalNoteListResponse> {
  const response = await apiClient.get<GoalNoteListResponse>(`/goals/${goalId}/notes`);
  return response.data;
}

export async function createGoalNote(goalId: number, body: string): Promise<GoalNote> {
  const response = await apiClient.post<GoalNote>(`/goals/${goalId}/notes`, { body });
  return response.data;
}

export async function deleteGoalNote(goalId: number, noteId: number): Promise<void> {
  await apiClient.delete(`/goals/${goalId}/notes/${noteId}`);
}

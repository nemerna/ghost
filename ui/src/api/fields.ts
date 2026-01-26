/**
 * API functions for Report Field and Project management
 */

import { fetchApi, postApi, putApi, deleteApi } from './client';
import type {
  FieldCreateRequest,
  FieldListResponse,
  FieldReorderRequest,
  FieldUpdateRequest,
  ProjectCreateRequest,
  ProjectReorderRequest,
  ProjectUpdateRequest,
  RedetectResponse,
  ReportField,
  ReportProject,
} from '@/types';

// =============================================================================
// Field API Functions
// =============================================================================

/**
 * List all report fields with their projects
 */
export async function listFields(): Promise<FieldListResponse> {
  return fetchApi<FieldListResponse>('/fields');
}

/**
 * Get a specific field by ID
 */
export async function getField(fieldId: number): Promise<ReportField> {
  return fetchApi<ReportField>(`/fields/${fieldId}`);
}

/**
 * Create a new report field
 */
export async function createField(data: FieldCreateRequest): Promise<ReportField> {
  return postApi<ReportField>('/fields', data);
}

/**
 * Update a report field
 */
export async function updateField(fieldId: number, data: FieldUpdateRequest): Promise<ReportField> {
  return putApi<ReportField>(`/fields/${fieldId}`, data);
}

/**
 * Delete a report field and all its projects
 */
export async function deleteField(fieldId: number): Promise<{ message: string }> {
  return deleteApi<{ message: string }>(`/fields/${fieldId}`);
}

/**
 * Reorder report fields
 */
export async function reorderFields(data: FieldReorderRequest): Promise<FieldListResponse> {
  return putApi<FieldListResponse>('/fields/reorder', data);
}

// =============================================================================
// Project API Functions
// =============================================================================

/**
 * Get a specific project by ID
 */
export async function getProject(projectId: number): Promise<ReportProject> {
  return fetchApi<ReportProject>(`/fields/projects/${projectId}`);
}

/**
 * Create a new project within a field
 */
export async function createProject(fieldId: number, data: ProjectCreateRequest): Promise<ReportProject> {
  return postApi<ReportProject>(`/fields/${fieldId}/projects`, data);
}

/**
 * Update a project
 */
export async function updateProject(projectId: number, data: ProjectUpdateRequest): Promise<ReportProject> {
  return putApi<ReportProject>(`/fields/projects/${projectId}`, data);
}

/**
 * Delete a project
 */
export async function deleteProject(projectId: number): Promise<{ message: string }> {
  return deleteApi<{ message: string }>(`/fields/projects/${projectId}`);
}

/**
 * Reorder projects within a field
 */
export async function reorderProjects(fieldId: number, data: ProjectReorderRequest): Promise<ReportField> {
  return putApi<ReportField>(`/fields/${fieldId}/projects/reorder`, data);
}

// =============================================================================
// Utility API Functions
// =============================================================================

/**
 * Re-run project detection on existing activities
 */
export async function redetectActivities(params?: {
  username?: string;
  limit?: number;
}): Promise<RedetectResponse> {
  const queryParams = new URLSearchParams();
  if (params?.username) queryParams.set('username', params.username);
  if (params?.limit) queryParams.set('limit', String(params.limit));
  
  const queryString = queryParams.toString();
  const url = `/fields/redetect${queryString ? `?${queryString}` : ''}`;
  
  return postApi<RedetectResponse>(url);
}

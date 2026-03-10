/**
 * Report API functions
 */

import apiClient from './client';
import type {
  ConsolidatedDraft,
  ConsolidatedDraftCreateRequest,
  ConsolidatedDraftListResponse,
  ConsolidatedDraftUpdateRequest,
  ConsolidatedReportResponse,
  ConsolidatedReportSnapshot,
  GeneratedReport,
  ManagementReport,
  ManagementReportCreateRequest,
  ManagementReportListResponse,
  SnapshotCreateRequest,
  SnapshotListResponse,
  TeamReportAggregate,
  TeamReportingProgress,
  WeeklyReport,
  WeeklyReportListResponse,
} from '@/types';

// =============================================================================
// Weekly Reports
// =============================================================================

export async function getMyWeeklyReports(params?: {
  limit?: number;
  offset?: number;
}): Promise<WeeklyReportListResponse> {
  const response = await apiClient.get<WeeklyReportListResponse>('/reports/weekly/my', { params });
  return response.data;
}

export async function generateWeeklyReport(weekOffset: number = 0): Promise<GeneratedReport> {
  const response = await apiClient.get<GeneratedReport>('/reports/weekly/generate', {
    params: { week_offset: weekOffset },
  });
  return response.data;
}

export async function saveWeeklyReport(data: {
  week_offset?: number;
  custom_title?: string;
  custom_summary?: string;
}): Promise<{ success: boolean; report_id: number; created: boolean; message: string }> {
  const response = await apiClient.post('/reports/weekly', data);
  return response.data;
}

export async function getWeeklyReport(reportId: number): Promise<WeeklyReport> {
  const response = await apiClient.get<WeeklyReport>(`/reports/weekly/${reportId}`);
  return response.data;
}

export async function deleteWeeklyReport(reportId: number): Promise<void> {
  await apiClient.delete(`/reports/weekly/${reportId}`);
}

export async function updateWeeklyReportVisibility(reportId: number, visibleToManager: boolean | null): Promise<WeeklyReport> {
  const response = await apiClient.patch<WeeklyReport>(`/reports/weekly/${reportId}/visibility`, {
    visible_to_manager: visibleToManager,
  });
  return response.data;
}

export async function getTeamWeeklyReports(teamId: number, params?: {
  week_start?: string;
  limit?: number;
  offset?: number;
}): Promise<WeeklyReportListResponse> {
  const response = await apiClient.get<WeeklyReportListResponse>(`/reports/weekly/team/${teamId}`, { params });
  return response.data;
}

// =============================================================================
// Management Reports
// =============================================================================

export async function listManagementReports(params?: {
  project_key?: string;
  author?: string;
  limit?: number;
  offset?: number;
}): Promise<ManagementReportListResponse> {
  const response = await apiClient.get<ManagementReportListResponse>('/reports/management', { params });
  return response.data;
}

export async function createManagementReport(data: ManagementReportCreateRequest): Promise<ManagementReport> {
  const response = await apiClient.post<ManagementReport>('/reports/management', data);
  return response.data;
}

export async function getManagementReport(reportId: number): Promise<ManagementReport> {
  const response = await apiClient.get<ManagementReport>(`/reports/management/${reportId}`);
  return response.data;
}

export async function updateManagementReport(
  reportId: number,
  data: Partial<ManagementReportCreateRequest>
): Promise<ManagementReport> {
  const response = await apiClient.put<ManagementReport>(`/reports/management/${reportId}`, data);
  return response.data;
}

export async function deleteManagementReport(reportId: number): Promise<void> {
  await apiClient.delete(`/reports/management/${reportId}`);
}

export async function updateManagementReportVisibility(reportId: number, visibleToManager: boolean | null): Promise<ManagementReport> {
  const response = await apiClient.patch<ManagementReport>(`/reports/management/${reportId}/visibility`, {
    visible_to_manager: visibleToManager,
  });
  return response.data;
}

export async function getTeamManagementReports(teamId: number, params?: {
  report_period?: string;
  limit?: number;
  offset?: number;
}): Promise<ManagementReportListResponse> {
  const response = await apiClient.get<ManagementReportListResponse>(`/reports/management/team/${teamId}`, { params });
  return response.data;
}

export async function getTeamReportAggregate(teamId: number, weekOffset: number = 0): Promise<TeamReportAggregate> {
  const response = await apiClient.get<TeamReportAggregate>(`/reports/management/aggregate/${teamId}`, {
    params: { week_offset: weekOffset },
  });
  return response.data;
}

export async function getTeamReportingProgress(teamId: number, weekOffset: number = 0): Promise<TeamReportingProgress> {
  const response = await apiClient.get<TeamReportingProgress>(`/reports/management/team/${teamId}/progress`, {
    params: { week_offset: weekOffset },
  });
  return response.data;
}

// =============================================================================
// Consolidated Reports
// =============================================================================

/**
 * Get consolidated report grouped by Field → Project → Entries
 */
export async function getConsolidatedReport(teamId: number, params?: {
  report_period?: string;
  limit?: number;
}): Promise<ConsolidatedReportResponse> {
  const response = await apiClient.get<ConsolidatedReportResponse>(`/reports/consolidated/${teamId}`, { params });
  return response.data;
}

/**
 * Get filtered consolidated report with only specified fields/projects
 * Useful for creating sub-reports for different stakeholders
 */
export async function getFilteredConsolidatedReport(teamId: number, params?: {
  field_ids?: number[];
  project_ids?: number[];
  report_period?: string;
  limit?: number;
}): Promise<ConsolidatedReportResponse> {
  // Convert arrays to comma-separated strings for query params
  const queryParams: Record<string, string | number | undefined> = {
    report_period: params?.report_period,
    limit: params?.limit,
  };
  
  if (params?.field_ids && params.field_ids.length > 0) {
    queryParams.field_ids = params.field_ids.join(',');
  }
  if (params?.project_ids && params.project_ids.length > 0) {
    queryParams.project_ids = params.project_ids.join(',');
  }
  
  const response = await apiClient.get<ConsolidatedReportResponse>(
    `/reports/consolidated/${teamId}/filtered`,
    { params: queryParams }
  );
  return response.data;
}

// =============================================================================
// Consolidated Report Drafts (Manager Edits)
// =============================================================================

/**
 * List consolidated drafts for a team
 */
export async function listConsolidatedDrafts(teamId: number, params?: {
  limit?: number;
  offset?: number;
}): Promise<ConsolidatedDraftListResponse> {
  const response = await apiClient.get<ConsolidatedDraftListResponse>(
    `/reports/consolidated-drafts/${teamId}`,
    { params }
  );
  return response.data;
}

/**
 * Get a specific consolidated draft
 */
export async function getConsolidatedDraft(teamId: number, draftId: number): Promise<ConsolidatedDraft> {
  const response = await apiClient.get<ConsolidatedDraft>(
    `/reports/consolidated-drafts/${teamId}/${draftId}`
  );
  return response.data;
}

/**
 * Create a new consolidated draft
 * If content is not provided, initializes from current consolidated report data
 */
export async function createConsolidatedDraft(
  teamId: number,
  data: ConsolidatedDraftCreateRequest
): Promise<ConsolidatedDraft> {
  const response = await apiClient.post<ConsolidatedDraft>(
    `/reports/consolidated-drafts/${teamId}`,
    data
  );
  return response.data;
}

/**
 * Update a consolidated draft
 */
export async function updateConsolidatedDraft(
  teamId: number,
  draftId: number,
  data: ConsolidatedDraftUpdateRequest
): Promise<ConsolidatedDraft> {
  const response = await apiClient.put<ConsolidatedDraft>(
    `/reports/consolidated-drafts/${teamId}/${draftId}`,
    data
  );
  return response.data;
}

/**
 * Delete a consolidated draft
 */
export async function deleteConsolidatedDraft(teamId: number, draftId: number): Promise<void> {
  await apiClient.delete(`/reports/consolidated-drafts/${teamId}/${draftId}`);
}

// =============================================================================
// Consolidated Report Snapshots (History)
// =============================================================================

/**
 * List consolidated report snapshots for a team
 */
export async function listConsolidatedSnapshots(
  teamId: number,
  params?: {
    report_period?: string;
    limit?: number;
  }
): Promise<SnapshotListResponse> {
  const response = await apiClient.get<SnapshotListResponse>(
    `/reports/consolidated-snapshots/${teamId}`,
    { params }
  );
  return response.data;
}

/**
 * Get a specific consolidated report snapshot
 */
export async function getConsolidatedSnapshot(
  teamId: number,
  snapshotId: number
): Promise<ConsolidatedReportSnapshot> {
  const response = await apiClient.get<ConsolidatedReportSnapshot>(
    `/reports/consolidated-snapshots/${teamId}/${snapshotId}`
  );
  return response.data;
}

/**
 * Create a manual snapshot of the current consolidated report
 */
export async function createConsolidatedSnapshot(
  teamId: number,
  data: SnapshotCreateRequest
): Promise<ConsolidatedReportSnapshot> {
  const response = await apiClient.post<ConsolidatedReportSnapshot>(
    `/reports/consolidated-snapshots/${teamId}`,
    data
  );
  return response.data;
}

/**
 * Delete a consolidated report snapshot
 */
export async function deleteConsolidatedSnapshot(
  teamId: number,
  snapshotId: number
): Promise<void> {
  await apiClient.delete(`/reports/consolidated-snapshots/${teamId}/${snapshotId}`);
}

/**
 * Report API functions
 */

import apiClient from './client';
import type {
  GeneratedReport,
  ManagementReport,
  ManagementReportCreateRequest,
  ManagementReportListResponse,
  TeamReportAggregate,
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

export async function getTeamReportAggregate(teamId: number, weekOffset: number = 0): Promise<TeamReportAggregate> {
  const response = await apiClient.get<TeamReportAggregate>(`/reports/management/aggregate/${teamId}`, {
    params: { week_offset: weekOffset },
  });
  return response.data;
}

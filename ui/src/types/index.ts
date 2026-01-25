/**
 * Type definitions for Jira MCP UI
 */

// =============================================================================
// User Types
// =============================================================================

export type UserRole = 'user' | 'manager' | 'admin';

export interface User {
  id: number;
  email: string;
  display_name: string | null;
  role: UserRole;
  preferences: Record<string, unknown>;
  first_seen: string | null;
  last_seen: string | null;
}

export interface UserListResponse {
  users: User[];
  total: number;
}

// =============================================================================
// Team Types
// =============================================================================

export interface TeamMember {
  id: number;
  email: string;
  display_name: string | null;
  role: UserRole;
  joined_at: string | null;
}

export interface Team {
  id: number;
  name: string;
  description: string | null;
  manager_id: number | null;
  manager_email: string | null;
  manager_name: string | null;
  member_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface TeamDetail extends Team {
  members: TeamMember[];
}

export interface TeamListResponse {
  teams: Team[];
  total: number;
}

// =============================================================================
// Activity Types
// =============================================================================

export type ActionType = 'view' | 'create' | 'update' | 'comment' | 'transition' | 'link' | 'other';

export type TicketSource = 'jira' | 'github';

export interface Activity {
  id: number;
  username: string;
  user_id: number | null;
  ticket_key: string;
  ticket_summary: string | null;
  ticket_source: TicketSource;
  project_key: string | null;
  github_repo: string | null;
  action_type: ActionType;
  action_details: Record<string, unknown> | null;
  timestamp: string;
}

export interface ActivityListResponse {
  activities: Activity[];
  total: number;
}

export interface ActivitySummary {
  total_activities: number;
  unique_tickets: number;
  by_action_type: Record<string, number>;
  by_project: Record<string, number>;
  by_source: Record<TicketSource, number>;
  period_start: string;
  period_end: string;
}

export interface ActivityCreateRequest {
  ticket_key: string;
  ticket_summary?: string;
  project_key?: string;
  github_repo?: string;
  action_type?: ActionType;
  action_details?: Record<string, unknown>;
}

// =============================================================================
// Report Types
// =============================================================================

export interface WeeklyReport {
  id: number;
  username: string;
  week_start: string;
  week_end: string;
  title: string;
  summary: string;
  content: string;
  tickets_count: number;
  projects: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface WeeklyReportListResponse {
  reports: WeeklyReport[];
  total: number;
}

export interface GeneratedReport {
  title: string;
  summary: string;
  content: string;
  week_start: string;
  week_end: string;
  tickets_count: number;
  projects: string[];
  statistics: {
    created: number;
    updated: number;
    commented: number;
    transitioned: number;
  };
}

export interface ManagementReport {
  id: number;
  username: string;
  title: string;
  project_key: string | null;
  report_period: string | null;
  content: string;
  referenced_tickets: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface ManagementReportListResponse {
  reports: ManagementReport[];
  total: number;
}

export interface ManagementReportCreateRequest {
  title: string;
  content: string;
  project_key?: string;
  report_period?: string;
  referenced_tickets?: string[];
}

export interface TeamReportAggregate {
  team_id: number;
  team_name: string;
  week_start: string;
  week_end: string;
  total_members: number;
  reports_submitted: number;
  total_tickets: number;
  all_projects: string[];
  member_summaries: Array<{
    username: string;
    title: string;
    summary: string;
    tickets_count: number;
  }>;
}

// =============================================================================
// API Response Types
// =============================================================================

export interface ApiError {
  error: string;
  message: string;
  detail?: string;
}

export interface SuccessMessage {
  message: string;
}

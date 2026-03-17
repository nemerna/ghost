/**
 * Type definitions for Ghost UI
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
// Visibility Types
// =============================================================================

export type VisibilityValue = 'shared' | 'private';

export interface VisibilitySettings {
  activity_logs: VisibilityValue;
  management_reports: VisibilityValue;
}

export interface VisibilitySettingsResponse {
  visibility_defaults: VisibilitySettings;
}

export interface VisibilityUpdateRequest {
  visible_to_manager: boolean | null;
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
  ticket_url: string | null;
  ticket_source: TicketSource;
  project_key: string | null;
  github_repo: string | null;
  action_type: ActionType;
  action_details: Record<string, unknown> | null;
  timestamp: string;
  visible_to_manager: boolean | null;
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

export interface ReportEntry {
  text: string;
  private: boolean;
  ticket_key?: string | null;
  detected_project_id?: number | null;
}

export interface ReportEntryInput {
  text: string;
  private?: boolean;
  ticket_key?: string;
  detected_project_id?: number | null;
}

export interface ManagementReport {
  id: number;
  username: string;
  title: string;
  project_key: string | null;
  report_period: string | null;
  content: string;
  entries?: ReportEntry[] | null;  // Parsed structured entries
  referenced_tickets: string[];
  created_at: string | null;
  updated_at: string | null;
  visible_to_manager: boolean | null;
}

export interface ManagementReportListResponse {
  reports: ManagementReport[];
  total: number;
}

export interface ManagementReportCreateRequest {
  title: string;
  content?: string;  // Legacy plain text content
  entries?: ReportEntryInput[];  // New structured entries
  project_key?: string;
  report_period?: string;
  referenced_tickets?: string[];
}

export type MemberReportingStatusValue = 'done' | 'in_progress' | 'missing';

export interface MemberReportingStatus {
  user_id: number;
  email: string;
  display_name: string | null;
  status: MemberReportingStatusValue;
  report_count: number;
  latest_report_title: string | null;
  latest_report_updated_at: string | null;
}

export interface TeamReportingProgressSummary {
  done: number;
  in_progress: number;
  missing: number;
  total: number;
}

export interface TeamReportingProgress {
  team_id: number;
  team_name: string;
  week_start: string;
  week_end: string;
  members: MemberReportingStatus[];
  summary: TeamReportingProgressSummary;
}

// =============================================================================
// Report Field & Project Types
// =============================================================================

export interface JiraComponentConfig {
  jira_project_key: string;
  component_name: string;
}

export interface ReportProject {
  id: number;
  field_id: number;
  parent_id: number | null;
  name: string;
  description: string | null;
  display_order: number;
  is_leaf: boolean;
  git_repos: string[];
  jira_components: JiraComponentConfig[];
  children: ReportProject[];
  created_at: string | null;
  updated_at: string | null;
}

export interface ReportField {
  id: number;
  name: string;
  description: string | null;
  display_order: number;
  projects: ReportProject[];
  created_at: string | null;
  updated_at: string | null;
}

export interface FieldListResponse {
  fields: ReportField[];
  total: number;
}

export interface FieldCreateRequest {
  name: string;
  description?: string;
}

export interface FieldUpdateRequest {
  name?: string;
  description?: string;
}

export interface FieldReorderRequest {
  field_ids: number[];
}

export interface ProjectCreateRequest {
  name: string;
  description?: string;
  parent_id?: number | null;
  git_repos?: string[];
  jira_components?: JiraComponentConfig[];
}

export interface ProjectUpdateRequest {
  name?: string;
  description?: string;
  parent_id?: number | null;
  git_repos?: string[];
  jira_components?: JiraComponentConfig[];
}

export interface ProjectReorderRequest {
  project_ids: number[];
}

export interface RedetectResponse {
  success: boolean;
  processed_count: number;
  updated_count: number;
  message: string;
}

// =============================================================================
// Consolidated Report Types
// =============================================================================

/** A single parsed entry from a user's report */
export interface ConsolidatedUserEntry {
  text: string;
  index: number;  // Position in the original report
}

/** A user's report in the consolidated view with parsed entries */
export interface ConsolidatedEntry {
  username: string;
  report_id: number;
  title: string;
  content: string;  // Combined markdown (for display/backwards compat)
  entries: ConsolidatedUserEntry[];  // Individual entries for editing
  report_period: string | null;
  created_at: string | null;
}

export interface ConsolidatedProject {
  id: number;
  name: string;
  description: string | null;
  parent_id: number | null;
  is_leaf: boolean;
  entries: ConsolidatedEntry[];
  children: ConsolidatedProject[];
}

export interface ConsolidatedField {
  id: number;
  name: string;
  description: string | null;
  projects: ConsolidatedProject[];
}

export interface ConsolidatedReportResponse {
  team_id: number;
  team_name: string;
  report_period: string | null;
  fields: ConsolidatedField[];
  uncategorized: ConsolidatedEntry[];
  total_entries: number;
}

// =============================================================================
// Consolidated Report Snapshot Types (History)
// =============================================================================

export type SnapshotType = 'auto' | 'manual';

export interface ConsolidatedReportSnapshot {
  id: number;
  team_id: number;
  created_by_id: number;
  report_period: string;
  snapshot_type: SnapshotType;
  label: string | null;
  content: ConsolidatedReportResponse;
  created_at: string;
}

export interface SnapshotListResponse {
  snapshots: ConsolidatedReportSnapshot[];
  total: number;
}

export interface SnapshotCreateRequest {
  report_period: string;
  label?: string;
}

// =============================================================================
// Consolidated Report Draft Types (Manager Edits)
// =============================================================================

export interface ConsolidatedDraftEntry {
  text: string;
  original_report_id?: number;
  original_username?: string;
  is_manager_added: boolean;
}

export interface ConsolidatedDraftProject {
  id: number;
  name: string;
  parent_id?: number | null;
  is_leaf?: boolean;
  entries: ConsolidatedDraftEntry[];
  children?: ConsolidatedDraftProject[];
}

export interface ConsolidatedDraftField {
  id: number;
  name: string;
  projects: ConsolidatedDraftProject[];
}

export interface ConsolidatedDraftContent {
  format: string;
  fields: ConsolidatedDraftField[];
  uncategorized: ConsolidatedDraftEntry[];
}

export interface ConsolidatedDraft {
  id: number;
  team_id: number;
  manager_id: number;
  title: string;
  report_period: string | null;
  content: ConsolidatedDraftContent;
  created_at: string | null;
  updated_at: string | null;
}

export interface ConsolidatedDraftListResponse {
  drafts: ConsolidatedDraft[];
  total: number;
}

export interface ConsolidatedDraftCreateRequest {
  title: string;
  report_period?: string;
  content?: ConsolidatedDraftContent;
}

export interface ConsolidatedDraftUpdateRequest {
  title?: string;
  report_period?: string;
  content?: ConsolidatedDraftContent;
}

// =============================================================================
// Email Distribution Template Types
// =============================================================================

export interface EmailDistributionTemplate {
  id: string;
  name: string;
  recipients: string[];
  subject_template: string;
  included_field_ids: number[];
  included_project_ids: number[];
  created_at: string | null;
  updated_at: string | null;
}

export interface EmailTemplateCreateRequest {
  name: string;
  recipients: string[];
  subject_template: string;
  included_field_ids?: number[];
  included_project_ids?: number[];
}

export interface EmailTemplateUpdateRequest {
  name?: string;
  recipients?: string[];
  subject_template?: string;
  included_field_ids?: number[];
  included_project_ids?: number[];
}

export interface EmailTemplateListResponse {
  templates: EmailDistributionTemplate[];
  total: number;
}

// =============================================================================
// Personal Access Token Types
// =============================================================================

export interface PersonalAccessToken {
  id: number;
  name: string;
  token_prefix: string;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string | null;
  is_revoked: boolean;
}

export interface PersonalAccessTokenCreateRequest {
  name: string;
  expires_at?: string | null;
}

export interface PersonalAccessTokenCreateResponse {
  id: number;
  name: string;
  token_prefix: string;
  token: string; // Raw token, shown only once
  expires_at: string | null;
  created_at: string | null;
}

export interface PersonalAccessTokenListResponse {
  tokens: PersonalAccessToken[];
  total: number;
}

// =============================================================================
// GitHub Token Config Types
// =============================================================================

export interface GitHubTokenConfig {
  id: number;
  name: string;
  patterns: string[];
  display_order: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface GitHubTokenConfigCreateRequest {
  name: string;
  patterns: string[];
}

export interface GitHubTokenConfigUpdateRequest {
  patterns?: string[];
  display_order?: number;
}

export interface GitHubTokenConfigListResponse {
  configs: GitHubTokenConfig[];
  total: number;
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

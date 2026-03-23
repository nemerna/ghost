/**
 * Management Reports page - create and view management reports
 * Managers can view team members' reports and manage consolidated reports
 * 
 * New UX Flow:
 * 1. Landing page shows a table of reports (latest, drafts, snapshots)
 * 2. Click a report to open detail view
 * 3. Detail view has review mode (read-only) and edit mode (per-project editing)
 */

import { useState, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardTitle,
  Content,
  Divider,
  Dropdown,
  DropdownItem,
  DropdownList,
  EmptyState,
  EmptyStateBody,
  ExpandableSection,
  Flex,
  FlexItem,
  Form,
  FormGroup,
  FormSelect,
  FormSelectOption,
  Label,
  MenuToggle,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  PageSection,
  Spinner,
  TextInput,
  Title,
  Tooltip,
} from '@patternfly/react-core';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from '@patternfly/react-table';
import {
  PlusIcon,
  CopyIcon,
  ArrowLeftIcon,
  PencilAltIcon,
  SaveIcon,
  TrashIcon,
  CubesIcon,
  EyeIcon,
  EyeSlashIcon,
  FolderOpenIcon,
  OutlinedFileAltIcon,
  EnvelopeIcon,
  CogIcon,
  CheckCircleIcon,
  InProgressIcon,
  ExclamationTriangleIcon,
  AngleLeftIcon,
  AngleRightIcon,
  UsersIcon,
} from '@patternfly/react-icons';
import { format, formatDistanceToNow } from 'date-fns';
import { marked } from 'marked';
import {
  listManagementReports,
  createManagementReport,
  updateManagementReport,
  deleteManagementReport,
  getTeamManagementReports,
  getConsolidatedReport,
  updateManagementReportVisibility,
  listConsolidatedDrafts,
  createConsolidatedDraft,
  updateConsolidatedDraft,
  deleteConsolidatedDraft,
  listConsolidatedSnapshots,
  deleteConsolidatedSnapshot,
  getTeamReportingProgress,
} from '@/api/reports';
import { listFields } from '@/api/fields';
import { listTeams } from '@/api/teams';
import { listEmailTemplates } from '@/api/users';
import { useAuth } from '@/auth';
import { StyledMarkdown } from '@/components/StyledMarkdown';
import { ReportEntryEditor, reportEntriesToInputs } from '@/components/ReportEntryEditor';
import { ProjectEntryEditor, type ProjectEntry } from '@/components/ProjectEntryEditor';
import { EmailTemplatesModal } from '@/components/EmailTemplatesModal';
import type {
  ManagementReportCreateRequest,
  ManagementReport,
  ReportEntryInput,
  ConsolidatedDraftContent,
  ConsolidatedDraft,
  ConsolidatedReportSnapshot,
  ConsolidatedReportResponse,
  EmailDistributionTemplate,
  MemberReportingStatus,
} from '@/types';

// Configure marked for safe HTML output
marked.setOptions({
  breaks: true,
  gfm: true,
});

// =============================================================================
// Types for the new UX
// =============================================================================

/** Type of report row in the table */
type ReportRowType = 'live' | 'draft' | 'snapshot';

/** Row in the reports table */
interface ReportRow {
  id: string;  // Unique identifier: "live", "draft-{id}", "snapshot-{id}"
  type: ReportRowType;
  title: string;
  period: string | null;
  entriesCount: number;
  modifiedAt: Date | null;
  data: ConsolidatedReportResponse | ConsolidatedDraft | ConsolidatedReportSnapshot;
}

/** View mode for the detail view */
type ViewMode = 'review' | 'edit';

// =============================================================================
// Main Component
// =============================================================================

export function ManagementReportsPage() {
  const queryClient = useQueryClient();
  const { isManager, isAdmin } = useAuth();
  const canViewTeams = isManager || isAdmin;

  // Team selection state
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);

  // Navigation state: which report is selected (null = table view)
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  
  // View mode for detail view
  const [viewMode, setViewMode] = useState<ViewMode>('review');
  
  // Copy success state
  const [copySuccess, setCopySuccess] = useState(false);

  // Gmail notification state
  const [gmailNotification, setGmailNotification] = useState<string | null>(null);

  // Gmail dropdown state
  const [gmailDropdownOpen, setGmailDropdownOpen] = useState(false);
  const [emailTemplatesModalOpen, setEmailTemplatesModalOpen] = useState(false);

  // Week offset for progress tracker (0 = current week)
  const [progressWeekOffset, setProgressWeekOffset] = useState(0);
  const [isProgressExpanded, setIsProgressExpanded] = useState(false);

  // Modal state (for creating new reports only - personal reports)
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newReportEntries, setNewReportEntries] = useState<ReportEntryInput[]>([{ text: '', private: false }]);
  const [newReportFormData, setNewReportFormData] = useState<Omit<ManagementReportCreateRequest, 'content' | 'entries'>>({
    title: '',
    project_key: '',
    report_period: '',
    referenced_tickets: [],
  });

  // Inline editing state for personal reports - tracks modified entries per report
  const [editedEntries, setEditedEntries] = useState<Record<number, ReportEntryInput[]>>({});

  // Track which personal reports are expanded (collapsed by default)
  const [expandedReports, setExpandedReports] = useState<Set<number>>(new Set());

  // ==========================================================================
  // Draft Editing State (for consolidated report editing)
  // ==========================================================================
  
  // Currently editing draft content
  const [editedDraftContent, setEditedDraftContent] = useState<ConsolidatedDraftContent | null>(null);
  // Draft title and period
  const [draftTitle, setDraftTitle] = useState('');
  const [draftReportPeriod, setDraftReportPeriod] = useState('');
  // Track if draft has unsaved changes
  const [hasDraftChanges, setHasDraftChanges] = useState(false);
  // Currently editing draft ID (null if new draft from live data)
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);

  // ==========================================================================
  // Data Fetching
  // ==========================================================================

  // Fetch teams (for managers/admins)
  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => listTeams({ all_teams: true }),
    enabled: canViewTeams,
  });

  // Fetch personal management reports (when no team selected)
  const { data: reportsData, isLoading: isReportsLoading } = useQuery({
    queryKey: ['managementReports', selectedTeamId],
    queryFn: () =>
      selectedTeamId
        ? getTeamManagementReports(selectedTeamId, { limit: 100 })
        : listManagementReports({ limit: 50 }),
  });

  // Fetch consolidated report (live data)
  const { data: consolidatedData, isLoading: isConsolidatedLoading } = useQuery({
    queryKey: ['consolidatedReport', selectedTeamId],
    queryFn: () => getConsolidatedReport(selectedTeamId!, { limit: 100 }),
    enabled: !!selectedTeamId,
  });

  // Fetch drafts for the team
  const { data: draftsData, isLoading: isDraftsLoading } = useQuery({
    queryKey: ['consolidatedDrafts', selectedTeamId],
    queryFn: () => listConsolidatedDrafts(selectedTeamId!, { limit: 50 }),
    enabled: !!selectedTeamId && canViewTeams,
  });

  // Fetch snapshots for the team
  const { data: snapshotsData, isLoading: isSnapshotsLoading } = useQuery({
    queryKey: ['consolidatedSnapshots', selectedTeamId],
    queryFn: () => listConsolidatedSnapshots(selectedTeamId!, { limit: 50 }),
    enabled: !!selectedTeamId && canViewTeams,
  });

  // Fetch team reporting progress
  const { data: progressData, isLoading: isProgressLoading } = useQuery({
    queryKey: ['teamReportingProgress', selectedTeamId, progressWeekOffset],
    queryFn: () => getTeamReportingProgress(selectedTeamId!, progressWeekOffset),
    enabled: !!selectedTeamId && canViewTeams,
  });

  // Fetch report fields/projects for per-entry project badges
  const { data: fieldsData, isError: fieldsError } = useQuery({
    queryKey: ['fields'],
    queryFn: listFields,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  });

  if (fieldsError) {
    console.warn('Failed to load report fields — ProjectBadge will be unavailable');
  }

  // Fetch email templates
  const { data: emailTemplatesData } = useQuery({
    queryKey: ['emailTemplates'],
    queryFn: listEmailTemplates,
    enabled: canViewTeams,
  });

  // ==========================================================================
  // Mutations
  // ==========================================================================

  // Delete snapshot mutation
  const deleteSnapshotMutation = useMutation({
    mutationFn: (snapshotId: number) => deleteConsolidatedSnapshot(selectedTeamId!, snapshotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consolidatedSnapshots', selectedTeamId] });
    },
  });

  // Create draft mutation
  const createDraftMutation = useMutation({
    mutationFn: (data: { title: string; report_period?: string; content?: ConsolidatedDraftContent }) =>
      createConsolidatedDraft(selectedTeamId!, data),
    onSuccess: (draft) => {
      queryClient.invalidateQueries({ queryKey: ['consolidatedDrafts', selectedTeamId] });
      setEditingDraftId(draft.id);
      setHasDraftChanges(false);
    },
  });

  // Update draft mutation
  const updateDraftMutation = useMutation({
    mutationFn: (data: { draftId: number; title?: string; report_period?: string; content?: ConsolidatedDraftContent }) =>
      updateConsolidatedDraft(selectedTeamId!, data.draftId, {
        title: data.title,
        report_period: data.report_period,
        content: data.content,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consolidatedDrafts', selectedTeamId] });
      setHasDraftChanges(false);
    },
  });

  // Delete draft mutation
  const deleteDraftMutation = useMutation({
    mutationFn: (draftId: number) => deleteConsolidatedDraft(selectedTeamId!, draftId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consolidatedDrafts', selectedTeamId] });
    },
  });

  // Create report mutation
  const createMutation = useMutation({
    mutationFn: createManagementReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managementReports'] });
      setIsModalOpen(false);
      resetCreateForm();
    },
  });

  // Update report mutation (for inline edits)
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<ManagementReportCreateRequest> }) =>
      updateManagementReport(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['managementReports'] });
      queryClient.invalidateQueries({ queryKey: ['consolidatedReport'] });
      // Clear edited state for this report
      const newEdited = { ...editedEntries };
      delete newEdited[variables.id];
      setEditedEntries(newEdited);
    },
  });

  // Delete report mutation
  const deleteMutation = useMutation({
    mutationFn: deleteManagementReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managementReports'] });
    },
  });

  // Update visibility mutation
  const visibilityMutation = useMutation({
    mutationFn: ({ id, visible }: { id: number; visible: boolean | null }) =>
      updateManagementReportVisibility(id, visible),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managementReports'] });
      queryClient.invalidateQueries({ queryKey: ['consolidatedReport'] });
    },
  });

  // ==========================================================================
  // Helper Functions
  // ==========================================================================

  // Reset create form to initial state
  const resetCreateForm = () => {
    setNewReportFormData({
      title: '',
      project_key: '',
      report_period: '',
      referenced_tickets: [],
    });
    setNewReportEntries([{ text: '', private: false }]);
  };

  // Build reports table rows
  const reportRows = useMemo((): ReportRow[] => {
    if (!selectedTeamId) return [];

    const rows: ReportRow[] = [];

    // Add live report row (always first if exists)
    if (consolidatedData && consolidatedData.total_entries > 0) {
      rows.push({
        id: 'live',
        type: 'live',
        title: 'Latest Report',
        period: consolidatedData.report_period,
        entriesCount: consolidatedData.total_entries,
        modifiedAt: null,
        data: consolidatedData,
      });
    }

    // Add draft rows
    if (draftsData?.drafts) {
      for (const draft of draftsData.drafts) {
        const entriesCount = draft.content.fields.reduce(
          (sum, field) => sum + field.projects.reduce(
            (pSum, project) => pSum + project.entries.length, 0
          ), 0
        ) + (draft.content.uncategorized?.length || 0);

        rows.push({
          id: `draft-${draft.id}`,
          type: 'draft',
          title: draft.title,
          period: draft.report_period,
          entriesCount,
          modifiedAt: draft.updated_at ? new Date(draft.updated_at) : draft.created_at ? new Date(draft.created_at) : null,
          data: draft,
        });
      }
    }

    // Add snapshot rows
    if (snapshotsData?.snapshots) {
      for (const snapshot of snapshotsData.snapshots) {
        rows.push({
          id: `snapshot-${snapshot.id}`,
          type: 'snapshot',
          title: snapshot.label || `Snapshot - ${snapshot.report_period}`,
          period: snapshot.report_period,
          entriesCount: snapshot.content.total_entries,
          modifiedAt: new Date(snapshot.created_at),
          data: snapshot,
        });
      }
    }

    // Sort by modified date (newest first), live always first
    rows.sort((a, b) => {
      if (a.type === 'live') return -1;
      if (b.type === 'live') return 1;
      if (!a.modifiedAt && !b.modifiedAt) return 0;
      if (!a.modifiedAt) return 1;
      if (!b.modifiedAt) return -1;
      return b.modifiedAt.getTime() - a.modifiedAt.getTime();
    });

    return rows;
  }, [selectedTeamId, consolidatedData, draftsData, snapshotsData]);

  // Get selected report data
  const selectedReportData = useMemo(() => {
    if (!selectedReportId) return null;
    return reportRows.find(r => r.id === selectedReportId) || null;
  }, [selectedReportId, reportRows]);

  // Get team members for user assignment
  const teamMembers = useMemo((): { email: string; displayName: string }[] => {
    if (!consolidatedData) return [];
    
    // Extract unique users from consolidated data
    const users = new Map<string, string>();
    
    for (const field of consolidatedData.fields) {
      for (const project of field.projects) {
        for (const entry of project.entries) {
          if (entry.username && !users.has(entry.username)) {
            users.set(entry.username, entry.username.split('@')[0]);
          }
        }
      }
    }
    
    for (const entry of consolidatedData.uncategorized) {
      if (entry.username && !users.has(entry.username)) {
        users.set(entry.username, entry.username.split('@')[0]);
      }
    }
    
    return Array.from(users.entries()).map(([email, displayName]) => ({
      email,
      displayName,
    }));
  }, [consolidatedData]);

  // ==========================================================================
  // Event Handlers
  // ==========================================================================

  const handleTeamChange = (_event: React.FormEvent<HTMLSelectElement>, value: string) => {
    if (value === 'my') {
      setSelectedTeamId(null);
    } else {
      setSelectedTeamId(Number(value));
    }
    // Reset navigation state when changing teams
    setSelectedReportId(null);
    setViewMode('review');
    setEditedDraftContent(null);
    setHasDraftChanges(false);
    setProgressWeekOffset(0);
  };

  // Open a report from the table
  const handleOpenReport = (reportId: string) => {
    const row = reportRows.find(r => r.id === reportId);
    if (!row) return;

    setSelectedReportId(reportId);
    setViewMode('review');
    
    // Initialize edit state based on report type
    if (row.type === 'live') {
      // Convert live data to draft content format
      const draftContent = convertConsolidatedToDraftContent(row.data as ConsolidatedReportResponse);
      setEditedDraftContent(draftContent);
      setDraftTitle(`Report - ${format(new Date(), 'MMM d, yyyy')}`);
      setDraftReportPeriod((row.data as ConsolidatedReportResponse).report_period || '');
      setEditingDraftId(null);
    } else if (row.type === 'draft') {
      const draft = row.data as ConsolidatedDraft;
      setEditedDraftContent(draft.content);
      setDraftTitle(draft.title);
      setDraftReportPeriod(draft.report_period || '');
      setEditingDraftId(draft.id);
    } else if (row.type === 'snapshot') {
      const snapshot = row.data as ConsolidatedReportSnapshot;
      const draftContent = convertConsolidatedToDraftContent(snapshot.content);
      setEditedDraftContent(draftContent);
      setDraftTitle(snapshot.label || `Snapshot - ${snapshot.report_period}`);
      setDraftReportPeriod(snapshot.report_period);
      setEditingDraftId(null);
    }
    
    setHasDraftChanges(false);
  };

  // Go back to table view
  const handleBack = () => {
    if (hasDraftChanges && !confirm('You have unsaved changes. Are you sure you want to discard them?')) {
      return;
    }
    setSelectedReportId(null);
    setViewMode('review');
    setEditedDraftContent(null);
    setHasDraftChanges(false);
    setEditingDraftId(null);
  };

  // Toggle view mode
  const handleToggleViewMode = () => {
    if (viewMode === 'edit' && hasDraftChanges) {
      if (!confirm('You have unsaved changes. Switch to review mode will not save them. Continue?')) {
        return;
      }
    }
    setViewMode(viewMode === 'review' ? 'edit' : 'review');
  };

  // Save draft
  const handleSaveDraft = () => {
    if (!editedDraftContent || !draftTitle) return;

    if (editingDraftId) {
      // Update existing draft
      updateDraftMutation.mutate({
        draftId: editingDraftId,
        title: draftTitle,
        report_period: draftReportPeriod || undefined,
        content: editedDraftContent,
      });
    } else {
      // Create new draft
      createDraftMutation.mutate({
        title: draftTitle,
        report_period: draftReportPeriod || undefined,
        content: editedDraftContent,
      });
    }
  };

  // Delete draft
  const handleDeleteDraft = (draftId: number) => {
    if (confirm('Are you sure you want to delete this draft?')) {
      deleteDraftMutation.mutate(draftId);
      // If we're viewing this draft, go back to table
      if (selectedReportId === `draft-${draftId}`) {
        handleBack();
      }
    }
  };

  // Delete snapshot
  const handleDeleteSnapshot = (snapshotId: number) => {
    if (confirm('Are you sure you want to delete this snapshot?')) {
      deleteSnapshotMutation.mutate(snapshotId);
      // If we're viewing this snapshot, go back to table
      if (selectedReportId === `snapshot-${snapshotId}`) {
        handleBack();
      }
    }
  };

  // Convert consolidated data to draft content format (supports hierarchical projects)
  const convertConsolidatedToDraftContent = useCallback((data: ConsolidatedReportResponse): ConsolidatedDraftContent => {
    // Recursive function to convert projects with children
    const convertProject = (project: typeof data.fields[0]['projects'][0]): ConsolidatedDraftContent['fields'][0]['projects'][0] => ({
      id: project.id,
      name: project.name,
      parent_id: project.parent_id,
      is_leaf: project.is_leaf,
      // Flatten user entries into individual entries (only for leaf projects)
      entries: project.entries.flatMap((userEntry) =>
        (userEntry.entries || []).length > 0
          ? userEntry.entries.map((entry) => ({
              text: entry.text,
              original_report_id: userEntry.report_id,
              original_username: userEntry.username,
              is_manager_added: false,
            }))
          : [{
              text: userEntry.content,
              original_report_id: userEntry.report_id,
              original_username: userEntry.username,
              is_manager_added: false,
            }]
      ),
      children: (project.children || []).map(convertProject),
    });

    return {
      format: 'consolidated_v1',
      fields: data.fields.map((field) => ({
        id: field.id,
        name: field.name,
        projects: field.projects.map(convertProject),
      })),
      uncategorized: data.uncategorized.flatMap((userEntry) =>
        (userEntry.entries || []).length > 0
          ? userEntry.entries.map((entry) => ({
              text: entry.text,
              original_report_id: userEntry.report_id,
              original_username: userEntry.username,
              is_manager_added: false,
            }))
          : [{
              text: userEntry.content,
              original_report_id: userEntry.report_id,
              original_username: userEntry.username,
              is_manager_added: false,
            }]
      ),
    };
  }, []);

  // Handle project entries change (supports nested projects)
  const handleProjectEntriesChange = useCallback((fieldId: number, projectId: number, newEntries: ProjectEntry[]) => {
    if (!editedDraftContent) return;

    // Recursive function to find and update a project in the tree
    type DraftProject = ConsolidatedDraftContent['fields'][0]['projects'][0];
    const findAndUpdateProject = (projects: DraftProject[]): boolean => {
      for (const project of projects) {
        if (project.id === projectId) {
          project.entries = newEntries.map(e => ({
            text: e.text,
            original_report_id: e.originalReportId,
            original_username: e.originalUsername,
            is_manager_added: e.isManagerAdded,
          }));
          return true;
        }
        if (project.children && findAndUpdateProject(project.children)) {
          return true;
        }
      }
      return false;
    };

    const newContent = { ...editedDraftContent };
    const field = newContent.fields.find((f) => f.id === fieldId);
    if (field && findAndUpdateProject(field.projects)) {
      setEditedDraftContent(newContent);
      setHasDraftChanges(true);
    }
  }, [editedDraftContent]);

  // Handle uncategorized entries change
  const handleUncategorizedEntriesChange = useCallback((newEntries: ProjectEntry[]) => {
    if (!editedDraftContent) return;

    const newContent = { ...editedDraftContent };
    newContent.uncategorized = newEntries.map(e => ({
      text: e.text,
      original_report_id: e.originalReportId,
      original_username: e.originalUsername,
      is_manager_added: e.isManagerAdded,
    }));
    setEditedDraftContent(newContent);
    setHasDraftChanges(true);
  }, [editedDraftContent]);

  // Generate markdown from draft content (supports hierarchical projects)
  const draftToMarkdown = useCallback((): string => {
    if (!editedDraftContent) return '';

    const lines: string[] = [];

    // Recursive function to render projects at the correct heading level
    type DraftProject = ConsolidatedDraftContent['fields'][0]['projects'][0];
    const renderProject = (project: DraftProject, level: number) => {
      const heading = '#'.repeat(Math.min(level, 6)); // Markdown supports up to h6
      lines.push(`${heading} ${project.name}`);
      lines.push('');

      // Only leaf projects have entries
      if (project.entries && project.entries.length > 0) {
        project.entries.forEach((entry) => {
          lines.push(`- ${entry.text}`);
        });
        lines.push('');
      }

      // Render children recursively
      if (project.children && project.children.length > 0) {
        project.children.forEach((child) => {
          renderProject(child, level + 1);
        });
      }
    };

    editedDraftContent.fields.forEach((field) => {
      lines.push(`# ${field.name}`);
      lines.push('');

      field.projects.forEach((project) => {
        renderProject(project, 2); // Start at h2 for projects
      });
    });

    if (editedDraftContent.uncategorized.length > 0) {
      lines.push('# Other');
      lines.push('');

      editedDraftContent.uncategorized.forEach((entry) => {
        lines.push(`- ${entry.text}`);
      });
      lines.push('');
    }

    return lines.join('\n');
  }, [editedDraftContent]);

  // Copy to clipboard
  const handleCopyToClipboard = async () => {
    try {
      const markdown = draftToMarkdown();
      const html = await marked.parse(markdown);

      const styledHtml = `
        <div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
          ${html}
        </div>
      `;

      const htmlBlob = new Blob([styledHtml], { type: 'text/html' });
      const textBlob = new Blob([markdown], { type: 'text/plain' });

      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': htmlBlob,
          'text/plain': textBlob,
        }),
      ]);

      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 3000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
      try {
        await navigator.clipboard.writeText(draftToMarkdown());
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 3000);
      } catch (fallbackErr) {
        console.error('Fallback copy also failed:', fallbackErr);
      }
    }
  };

  // ==========================================================================
  // Gmail Send Functionality
  // ==========================================================================

  /**
   * Generate filtered markdown for a template (only include specified fields/projects)
   * Supports hierarchical projects
   */
  const generateFilteredMarkdown = useCallback((template: EmailDistributionTemplate | null): string => {
    if (!editedDraftContent) return '';

    const lines: string[] = [];
    const hasFieldFilter = template && template.included_field_ids.length > 0;
    const hasProjectFilter = template && template.included_project_ids.length > 0;

    // Recursive function to check if a project or any descendant is in the filter
    type DraftProject = ConsolidatedDraftContent['fields'][0]['projects'][0];
    const projectOrDescendantInFilter = (project: DraftProject, filterIds: number[]): boolean => {
      if (filterIds.includes(project.id)) return true;
      return (project.children || []).some(child => projectOrDescendantInFilter(child, filterIds));
    };

    // Recursive function to filter projects
    const filterProjects = (projects: DraftProject[], filterIds: number[] | null): DraftProject[] => {
      if (!filterIds) return projects;
      return projects
        .filter(project => projectOrDescendantInFilter(project, filterIds))
        .map(project => ({
          ...project,
          children: filterProjects(project.children || [], filterIds),
        }));
    };

    // Recursive function to render projects
    const renderProject = (project: DraftProject, level: number) => {
      const heading = '#'.repeat(Math.min(level, 6));
      lines.push(`${heading} ${project.name}`);
      lines.push('');

      if (project.entries && project.entries.length > 0) {
        project.entries.forEach((entry) => {
          lines.push(`- ${entry.text}`);
        });
        lines.push('');
      }

      (project.children || []).forEach((child) => {
        renderProject(child, level + 1);
      });
    };

    editedDraftContent.fields.forEach((field) => {
      // Skip field if not in filter
      if (hasFieldFilter && !template.included_field_ids.includes(field.id)) {
        return;
      }

      const filteredProjects = filterProjects(
        field.projects,
        hasProjectFilter ? template.included_project_ids : null
      );

      // Skip field if no projects after filtering
      if (filteredProjects.length === 0) return;

      lines.push(`# ${field.name}`);
      lines.push('');

      filteredProjects.forEach((project) => {
        renderProject(project, 2);
      });
    });

    // Include uncategorized only if no filters applied
    if (!hasFieldFilter && !hasProjectFilter && editedDraftContent.uncategorized.length > 0) {
      lines.push('# Other');
      lines.push('');

      editedDraftContent.uncategorized.forEach((entry) => {
        lines.push(`- ${entry.text}`);
      });
      lines.push('');
    }

    return lines.join('\n');
  }, [editedDraftContent]);

  /**
   * Process subject template with placeholders
   */
  const processSubjectTemplate = useCallback((subjectTemplate: string): string => {
    const teamName = teamsData?.teams.find(t => t.id === selectedTeamId)?.name || 'Team';
    const period = draftReportPeriod || 'Report';
    const date = format(new Date(), 'MMM d, yyyy');

    return subjectTemplate
      .replace(/\{\{team_name\}\}/g, teamName)
      .replace(/\{\{period\}\}/g, period)
      .replace(/\{\{date\}\}/g, date);
  }, [teamsData, selectedTeamId, draftReportPeriod]);

  /**
   * Open Gmail compose window with pre-filled content
   * Converts markdown to HTML and copies to clipboard for pasting
   */
  const openGmailCompose = useCallback(async (
    recipients: string[],
    subject: string,
    body: string
  ) => {
    try {
      // Convert markdown to HTML for clickable links
      const html = await marked.parse(body);
      const styledHtml = `
        <div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
          ${html}
        </div>
      `;

      // Copy HTML to clipboard
      // Note: ClipboardItem with text/html has limited support in older Safari versions
      // The fallback catch block handles browsers that don't support this feature
      const htmlBlob = new Blob([styledHtml], { type: 'text/html' });
      const textBlob = new Blob([body], { type: 'text/plain' });

      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': htmlBlob,
          'text/plain': textBlob,
        }),
      ]);

      // Show notification first (before opening Gmail to avoid focus issues)
      setGmailNotification('Report copied to clipboard with formatting! Paste it into the Gmail compose window (Ctrl+V or Cmd+V).');

      // Auto-dismiss notification after 8 seconds
      setTimeout(() => setGmailNotification(null), 8000);

      // Open Gmail compose with recipients and subject
      const baseUrl = 'https://mail.google.com/mail/?view=cm&fs=1';
      const toParam = `&to=${encodeURIComponent(recipients.join(','))}`;
      const subjectParam = `&su=${encodeURIComponent(subject)}`;
      const gmailUrl = baseUrl + toParam + subjectParam;

      // Open Gmail in new tab
      window.open(gmailUrl, '_blank');
    } catch (err) {
      console.error('Failed to copy formatted report:', err);

      // Fallback: open Gmail with plain text body
      const baseUrl = 'https://mail.google.com/mail/?view=cm&fs=1';
      const toParam = `&to=${encodeURIComponent(recipients.join(','))}`;
      const subjectParam = `&su=${encodeURIComponent(subject)}`;
      const bodyParam = `&body=${encodeURIComponent(body)}`;
      const gmailUrl = baseUrl + toParam + subjectParam + bodyParam;
      window.open(gmailUrl, '_blank');

      setGmailNotification('Opened Gmail with plain text (clipboard copy not supported on this browser).');
      setTimeout(() => setGmailNotification(null), 8000);
    }
  }, []);

  /**
   * Handle sending report via Gmail
   */
  const handleSendViaGmail = useCallback(async (template: EmailDistributionTemplate | null) => {
    setGmailDropdownOpen(false);

    if (template) {
      // Use template settings
      const body = generateFilteredMarkdown(template);
      const subject = processSubjectTemplate(template.subject_template);
      await openGmailCompose(template.recipients, subject, body);
    } else {
      // Full report - prompt for recipients
      const recipientsInput = prompt('Enter recipient email addresses (comma-separated):');
      if (!recipientsInput) return;

      const recipients = recipientsInput.split(',').map(e => e.trim()).filter(e => e.includes('@'));
      if (recipients.length === 0) {
        alert('No valid email addresses provided');
        return;
      }

      const teamName = teamsData?.teams.find(t => t.id === selectedTeamId)?.name || 'Team';
      const period = draftReportPeriod || 'Report';
      const subject = `${teamName} - Weekly Report - ${period}`;
      const body = draftToMarkdown();

      await openGmailCompose(recipients, subject, body);
    }
  }, [generateFilteredMarkdown, processSubjectTemplate, openGmailCompose, draftToMarkdown, teamsData, selectedTeamId, draftReportPeriod]);

  // ==========================================================================
  // Personal Reports Handlers
  // ==========================================================================

  // Check if a report has unsaved changes
  const hasChanges = (reportId: number) => reportId in editedEntries;

  // Get entries to display (edited if modified, otherwise original)
  const getDisplayEntries = (report: ManagementReport): ReportEntryInput[] => {
    if (editedEntries[report.id]) {
      return editedEntries[report.id];
    }
    return reportEntriesToInputs(report.entries);
  };

  // Handle inline entry changes
  const handleEntryChange = (reportId: number, entries: ReportEntryInput[]) => {
    setEditedEntries({ ...editedEntries, [reportId]: entries });
  };

  // Cancel inline editing
  const handleCancelEdit = (reportId: number) => {
    const newEdited = { ...editedEntries };
    delete newEdited[reportId];
    setEditedEntries(newEdited);
  };

  // Save inline edits
  const handleSaveEdit = (reportId: number) => {
    const entries = editedEntries[reportId];
    if (!entries) return;

    updateMutation.mutate({
      id: reportId,
      data: { entries: entries.filter((e) => e.text.trim().length > 0) },
    });
  };

  const handleToggleVisibility = (report: ManagementReport) => {
    let newValue: boolean | null;
    if (report.visible_to_manager === null) {
      newValue = true;
    } else if (report.visible_to_manager === true) {
      newValue = false;
    } else {
      newValue = null;
    }
    visibilityMutation.mutate({ id: report.id, visible: newValue });
  };

  const getVisibilityInfo = (report: ManagementReport) => {
    if (report.visible_to_manager === true) {
      return {
        icon: <EyeIcon />,
        label: 'Visible to Manager',
        tooltip: 'This report is shared with your manager. Click to hide it.',
        color: '#3e8635',
        labelColor: 'green' as const,
      };
    } else if (report.visible_to_manager === false) {
      return {
        icon: <EyeSlashIcon />,
        label: 'Hidden from Manager',
        tooltip: 'This report is hidden from your manager. Click to reset to default.',
        color: '#c9190b',
        labelColor: 'red' as const,
      };
    } else {
      return {
        icon: <EyeIcon />,
        label: 'Default Visibility',
        tooltip: 'Using default visibility rules. Click to explicitly share with manager.',
        color: '#6a6e73',
        labelColor: 'grey' as const,
      };
    }
  };

  const handleOpenCreateModal = () => {
    resetCreateForm();
    setIsModalOpen(true);
  };

  const handleCreateReport = () => {
    const hasEntries = newReportEntries.some((e) => e.text.trim().length > 0);
    if (!newReportFormData.title || !hasEntries) return;

    const entries = newReportEntries.filter((e) => e.text.trim().length > 0);
    createMutation.mutate({
      ...newReportFormData,
      entries,
    });
  };

  const handleDelete = (reportId: number) => {
    if (confirm('Are you sure you want to delete this report?')) {
      deleteMutation.mutate(reportId);
    }
  };

  // ==========================================================================
  // Render Functions
  // ==========================================================================

  // Render team reporting progress overview (compact collapsible card)
  const renderProgressOverview = () => {
    const statusLabel = (member: MemberReportingStatus) => {
      switch (member.status) {
        case 'done':
          return <Label color="green" icon={<CheckCircleIcon />} isCompact>Done</Label>;
        case 'in_progress':
          return <Label color="orange" icon={<InProgressIcon />} isCompact>In Progress</Label>;
        case 'missing':
          return <Label color="red" icon={<ExclamationTriangleIcon />} isCompact>Missing</Label>;
      }
    };

    // Build the toggle content: inline summary badges + week nav
    const summaryToggle = (
      <Flex
        alignItems={{ default: 'alignItemsCenter' }}
        style={{ gap: '0.75rem', width: '100%' }}
        justifyContent={{ default: 'justifyContentSpaceBetween' }}
      >
        <FlexItem>
          <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ gap: '0.5rem' }}>
            <FlexItem><UsersIcon /></FlexItem>
            <FlexItem><strong>Reporting Progress</strong></FlexItem>
            {isProgressLoading ? (
              <FlexItem><Spinner size="sm" /></FlexItem>
            ) : progressData ? (
              <>
                <FlexItem>
                  <Label color="green" isCompact icon={<CheckCircleIcon />}>
                    {progressData.summary.done} Done
                  </Label>
                </FlexItem>
                <FlexItem>
                  <Label color="orange" isCompact icon={<InProgressIcon />}>
                    {progressData.summary.in_progress} In Progress
                  </Label>
                </FlexItem>
                <FlexItem>
                  <Label color="red" isCompact icon={<ExclamationTriangleIcon />}>
                    {progressData.summary.missing} Missing
                  </Label>
                </FlexItem>
              </>
            ) : null}
          </Flex>
        </FlexItem>
        <FlexItem>
          <Flex
            alignItems={{ default: 'alignItemsCenter' }}
            style={{ gap: '0.25rem' }}
            onClick={(e) => e.stopPropagation()}
          >
            <FlexItem>
              <Tooltip content="Previous week">
                <Button
                  variant="plain"
                  size="sm"
                  onClick={() => setProgressWeekOffset(Math.max(progressWeekOffset - 1, -52))}
                  icon={<AngleLeftIcon />}
                  aria-label="Previous week"
                />
              </Tooltip>
            </FlexItem>
            <FlexItem>
              <Button
                variant="link"
                size="sm"
                onClick={() => setProgressWeekOffset(0)}
                isDisabled={progressWeekOffset === 0}
                style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}
              >
                {progressData
                  ? `${progressData.week_start} — ${progressData.week_end}`
                  : 'This Week'}
              </Button>
            </FlexItem>
            <FlexItem>
              <Tooltip content="Next week">
                <Button
                  variant="plain"
                  size="sm"
                  onClick={() => setProgressWeekOffset(Math.min(progressWeekOffset + 1, 0))}
                  isDisabled={progressWeekOffset >= 0}
                  icon={<AngleRightIcon />}
                  aria-label="Next week"
                />
              </Tooltip>
            </FlexItem>
          </Flex>
        </FlexItem>
      </Flex>
    );

    return (
      <Card isCompact style={{ marginBottom: '1rem' }}>
        <CardBody style={{ paddingBottom: isProgressExpanded ? 0 : undefined }}>
          <ExpandableSection
            toggleContent={summaryToggle}
            isExpanded={isProgressExpanded}
            onToggle={(_event, expanded) => setIsProgressExpanded(expanded)}
            isIndented
          >
            {progressData && progressData.members.length > 0 && (
              <Table aria-label="Team reporting progress" variant="compact">
                <Thead>
                  <Tr>
                    <Th width={35}>Member</Th>
                    <Th width={15}>Status</Th>
                    <Th width={35}>Latest Report</Th>
                    <Th width={15}>Updated</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {progressData.members.map((member) => (
                    <Tr key={member.user_id}>
                      <Td dataLabel="Member">
                        {member.display_name || member.email}
                        {member.display_name && (
                          <span style={{ color: '#6a6e73', fontSize: '0.85rem', marginLeft: '0.5rem' }}>
                            {member.email}
                          </span>
                        )}
                      </Td>
                      <Td dataLabel="Status">
                        {statusLabel(member)}
                      </Td>
                      <Td dataLabel="Latest Report">
                        {member.latest_report_title || <span style={{ color: '#6a6e73' }}>—</span>}
                        {member.report_count > 1 && (
                          <Label color="grey" isCompact style={{ marginLeft: '0.5rem' }}>
                            +{member.report_count - 1} more
                          </Label>
                        )}
                      </Td>
                      <Td dataLabel="Updated">
                        {member.latest_report_updated_at
                          ? formatDistanceToNow(new Date(member.latest_report_updated_at), { addSuffix: true })
                          : <span style={{ color: '#6a6e73' }}>—</span>
                        }
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}
          </ExpandableSection>
        </CardBody>
      </Card>
    );
  };

  // Render the reports table (landing page for team view)
  const renderReportsTable = () => {
    const isLoading = isConsolidatedLoading || isDraftsLoading || isSnapshotsLoading;

    if (isLoading) {
      return (
        <Card>
          <CardBody>
            <Flex justifyContent={{ default: 'justifyContentCenter' }}>
              <Spinner size="xl" />
            </Flex>
          </CardBody>
        </Card>
      );
    }

    if (reportRows.length === 0) {
      return (
        <Card>
          <CardBody>
            <EmptyState
              titleText="No reports available"
              icon={OutlinedFileAltIcon}
              headingLevel="h4"
            >
              <EmptyStateBody>
                Team members haven't submitted any reports yet, or no reports are visible to you.
              </EmptyStateBody>
            </EmptyState>
          </CardBody>
        </Card>
      );
    }

    return (
      <Card>
        <CardTitle>
          <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
            <FlexItem>
              <CubesIcon style={{ marginRight: '0.5rem' }} />
              Team Reports
              <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                {reportRows.length} {reportRows.length === 1 ? 'report' : 'reports'}
              </Label>
            </FlexItem>
          </Flex>
        </CardTitle>
        <CardBody>
          <Table aria-label="Reports table" variant="compact">
            <Thead>
              <Tr>
                <Th width={30}>Title</Th>
                <Th width={15}>Period</Th>
                <Th width={10}>Status</Th>
                <Th width={10}>Entries</Th>
                <Th width={15}>Modified</Th>
                <Th width={20}>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {reportRows.map((row) => (
                <Tr key={row.id}>
                  <Td dataLabel="Title">
                    <Button
                      variant="link"
                      onClick={() => handleOpenReport(row.id)}
                      style={{ padding: 0, textAlign: 'left' }}
                    >
                      {row.title}
                    </Button>
                  </Td>
                  <Td dataLabel="Period">
                    {row.period || '-'}
                  </Td>
                  <Td dataLabel="Status">
                    <Label
                      color={row.type === 'live' ? 'green' : row.type === 'draft' ? 'orange' : 'blue'}
                      isCompact
                    >
                      {row.type === 'live' ? 'Live' : row.type === 'draft' ? 'Draft' : 'Snapshot'}
                    </Label>
                  </Td>
                  <Td dataLabel="Entries">
                    {row.entriesCount}
                  </Td>
                  <Td dataLabel="Modified">
                    {row.modifiedAt
                      ? formatDistanceToNow(row.modifiedAt, { addSuffix: true })
                      : row.type === 'live' ? 'Live data' : '-'}
                  </Td>
                  <Td dataLabel="Actions">
                    <Flex style={{ gap: '0.5rem' }}>
                      <FlexItem>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleOpenReport(row.id)}
                          icon={<FolderOpenIcon />}
                        >
                          Open
                        </Button>
                      </FlexItem>
                      {row.type === 'draft' && (
                        <FlexItem>
                          <Tooltip content="Delete draft">
                            <Button
                              variant="plain"
                              isDanger
                              size="sm"
                              onClick={() => handleDeleteDraft((row.data as ConsolidatedDraft).id)}
                              isLoading={deleteDraftMutation.isPending}
                            >
                              <TrashIcon />
                            </Button>
                          </Tooltip>
                        </FlexItem>
                      )}
                      {row.type === 'snapshot' && (
                        <FlexItem>
                          <Tooltip content="Delete snapshot">
                            <Button
                              variant="plain"
                              isDanger
                              size="sm"
                              onClick={() => handleDeleteSnapshot((row.data as ConsolidatedReportSnapshot).id)}
                              isLoading={deleteSnapshotMutation.isPending}
                            >
                              <TrashIcon />
                            </Button>
                          </Tooltip>
                        </FlexItem>
                      )}
                    </Flex>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </CardBody>
      </Card>
    );
  };

  // Render the report detail view
  const renderReportDetailView = () => {
    if (!selectedReportData || !editedDraftContent) return null;

    const isEditing = viewMode === 'edit';

    return (
      <>
        {/* Header with navigation and actions */}
        <Card style={{ marginBottom: '1rem', border: isEditing ? '2px solid #0066cc' : undefined }}>
          <CardBody>
            <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
              <FlexItem>
                <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ gap: '1rem' }}>
                  <FlexItem>
                    <Button
                      variant="link"
                      icon={<ArrowLeftIcon />}
                      onClick={handleBack}
                    >
                      Back
                    </Button>
                  </FlexItem>
                  <FlexItem>
                    {isEditing ? (
                      <TextInput
                        value={draftTitle}
                        onChange={(_e, val) => { setDraftTitle(val); setHasDraftChanges(true); }}
                        aria-label="Report title"
                        style={{ fontWeight: 'bold', fontSize: '1.25rem', minWidth: '300px' }}
                      />
                    ) : (
                      <Title headingLevel="h2">{draftTitle}</Title>
                    )}
                  </FlexItem>
                  <FlexItem>
                    <Label
                      color={selectedReportData.type === 'live' ? 'green' : selectedReportData.type === 'draft' ? 'orange' : 'blue'}
                    >
                      {selectedReportData.type === 'live' ? 'Live' : selectedReportData.type === 'draft' ? 'Draft' : 'Snapshot'}
                    </Label>
                  </FlexItem>
                  {hasDraftChanges && (
                    <FlexItem>
                      <Label color="orange">Unsaved Changes</Label>
                    </FlexItem>
                  )}
                </Flex>
              </FlexItem>
              <FlexItem>
                <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ gap: '0.5rem' }}>
                  {isEditing && (
                    <FlexItem>
                      <TextInput
                        value={draftReportPeriod}
                        onChange={(_e, val) => { setDraftReportPeriod(val); setHasDraftChanges(true); }}
                        placeholder="Report period (e.g., Week 4, Jan 2026)"
                        aria-label="Report period"
                        style={{ minWidth: '200px' }}
                      />
                    </FlexItem>
                  )}
                  <FlexItem>
                    <Button
                      variant={isEditing ? 'secondary' : 'primary'}
                      icon={isEditing ? <EyeIcon /> : <PencilAltIcon />}
                      onClick={handleToggleViewMode}
                    >
                      {isEditing ? 'Review' : 'Edit'}
                    </Button>
                  </FlexItem>
                  {isEditing && (
                    <FlexItem>
                      <Button
                        variant="primary"
                        icon={<SaveIcon />}
                        onClick={handleSaveDraft}
                        isLoading={createDraftMutation.isPending || updateDraftMutation.isPending}
                        isDisabled={!draftTitle}
                      >
                        {editingDraftId ? 'Save' : 'Save as Draft'}
                      </Button>
                    </FlexItem>
                  )}
                  <FlexItem>
                    <Button
                      variant="secondary"
                      icon={<CopyIcon />}
                      onClick={handleCopyToClipboard}
                    >
                      {copySuccess ? 'Copied!' : 'Copy'}
                    </Button>
                  </FlexItem>
                  <FlexItem>
                    <Dropdown
                      isOpen={gmailDropdownOpen}
                      onOpenChange={(isOpen) => setGmailDropdownOpen(isOpen)}
                      toggle={(toggleRef) => (
                        <MenuToggle
                          ref={toggleRef}
                          onClick={() => setGmailDropdownOpen(!gmailDropdownOpen)}
                          isExpanded={gmailDropdownOpen}
                          variant="primary"
                        >
                          <EnvelopeIcon style={{ marginRight: '0.5rem' }} />
                          Send via Gmail
                        </MenuToggle>
                      )}
                    >
                      <DropdownList>
                        <DropdownItem
                          key="full-report"
                          onClick={() => handleSendViaGmail(null)}
                          description="Enter recipients manually"
                        >
                          Send Full Report
                        </DropdownItem>
                        {emailTemplatesData?.templates && emailTemplatesData.templates.length > 0 && (
                          <>
                            <Divider key="divider-templates" />
                            {emailTemplatesData.templates.map((template) => (
                              <DropdownItem
                                key={template.id}
                                onClick={() => handleSendViaGmail(template)}
                                description={`${template.recipients.length} recipient(s)`}
                              >
                                {template.name}
                              </DropdownItem>
                            ))}
                          </>
                        )}
                        <Divider key="divider-manage" />
                        <DropdownItem
                          key="manage-templates"
                          onClick={() => {
                            setGmailDropdownOpen(false);
                            setEmailTemplatesModalOpen(true);
                          }}
                          icon={<CogIcon />}
                        >
                          Manage Templates...
                        </DropdownItem>
                      </DropdownList>
                    </Dropdown>
                  </FlexItem>
                </Flex>
              </FlexItem>
            </Flex>
          </CardBody>
        </Card>

        {copySuccess && (
          <Alert
            variant="success"
            isInline
            title="Report copied to clipboard! You can now paste it in Gmail."
            style={{ marginBottom: '1rem' }}
          />
        )}

        {gmailNotification && (
          <Alert
            variant="success"
            isInline
            title={gmailNotification}
            style={{ marginBottom: '1rem' }}
          />
        )}

        {/* Report content - either review or edit mode */}
        {isEditing ? (
          // Edit mode - show ProjectEntryEditor per project (supports hierarchy)
          <>
            {editedDraftContent.fields.map((field) => {
              // Count total projects including nested
              type DraftProject = ConsolidatedDraftContent['fields'][0]['projects'][0];
              const countProjects = (projects: DraftProject[]): number =>
                projects.reduce((sum, p) => sum + 1 + countProjects(p.children || []), 0);
              
              // Recursive component to render project tree in edit mode
              const renderEditableProject = (project: DraftProject, depth: number = 0) => {
                const hasChildren = project.children && project.children.length > 0;
                const isLeaf = project.is_leaf !== false && !hasChildren;
                
                return (
                  <div key={project.id} style={{ marginLeft: depth > 0 ? '1.5rem' : 0 }}>
                    {isLeaf ? (
                      // Leaf project - show entry editor
                      <ProjectEntryEditor
                        projectId={project.id}
                        projectName={project.name}
                        entries={project.entries.map(e => ({
                          text: e.text,
                          originalReportId: e.original_report_id,
                          originalUsername: e.original_username,
                          isManagerAdded: e.is_manager_added,
                        }))}
                        teamMembers={teamMembers}
                        isEditing={true}
                        onEntriesChange={(newEntries) => handleProjectEntriesChange(field.id, project.id, newEntries)}
                      />
                    ) : (
                      // Non-leaf project - show as header with children
                      <div style={{ marginBottom: '1rem' }}>
                        <div style={{ 
                          fontWeight: 600, 
                          fontSize: depth === 0 ? '1.1rem' : '1rem',
                          marginBottom: '0.5rem',
                          color: '#151515',
                          borderBottom: depth === 0 ? '1px solid #d2d2d2' : 'none',
                          paddingBottom: depth === 0 ? '0.25rem' : 0,
                        }}>
                          {project.name}
                        </div>
                        {project.children?.map((child) => renderEditableProject(child, depth + 1))}
                      </div>
                    )}
                  </div>
                );
              };

              return (
                <Card key={field.id} style={{ marginBottom: '1rem' }}>
                  <CardTitle>
                    <CubesIcon style={{ marginRight: '0.5rem' }} />
                    {field.name}
                    <Label color="purple" style={{ marginLeft: '0.5rem' }}>
                      {countProjects(field.projects)} {countProjects(field.projects) === 1 ? 'project' : 'projects'}
                    </Label>
                  </CardTitle>
                  <CardBody>
                    {field.projects.map((project) => renderEditableProject(project))}
                  </CardBody>
                </Card>
              );
            })}

            {/* Uncategorized entries */}
            {editedDraftContent.uncategorized.length > 0 && (
              <Card style={{ marginBottom: '1rem' }}>
                <CardTitle>
                  Other / Uncategorized
                  <Label color="grey" style={{ marginLeft: '0.5rem' }}>
                    {editedDraftContent.uncategorized.length} {editedDraftContent.uncategorized.length === 1 ? 'entry' : 'entries'}
                  </Label>
                </CardTitle>
                <CardBody>
                  <ProjectEntryEditor
                    projectId={-1}
                    projectName="Uncategorized"
                    entries={editedDraftContent.uncategorized.map(e => ({
                      text: e.text,
                      originalReportId: e.original_report_id,
                      originalUsername: e.original_username,
                      isManagerAdded: e.is_manager_added,
                    }))}
                    teamMembers={teamMembers}
                    isEditing={true}
                    onEntriesChange={handleUncategorizedEntriesChange}
                  />
                </CardBody>
              </Card>
            )}
          </>
        ) : (
          // Review mode - show formatted markdown
          <Card>
            <CardBody>
              <StyledMarkdown maxHeight="800px">{draftToMarkdown()}</StyledMarkdown>
            </CardBody>
          </Card>
        )}
      </>
    );
  };

  // Render personal reports view (when no team selected)
  const renderPersonalReports = () => {
    if (isReportsLoading) {
      return (
        <Flex justifyContent={{ default: 'justifyContentCenter' }}>
          <Spinner size="xl" />
        </Flex>
      );
    }

    if (!reportsData?.reports.length) {
      return (
        <Card>
          <CardBody>
            <EmptyState
              titleText="No reports yet"
              icon={OutlinedFileAltIcon}
              headingLevel="h4"
            >
              <EmptyStateBody>
                Click "Create Report" to add your first management report.
              </EmptyStateBody>
            </EmptyState>
          </CardBody>
        </Card>
      );
    }

    return reportsData.reports.map((report) => {
      const visInfo = getVisibilityInfo(report);
      const isEditingReport = hasChanges(report.id);
      const displayEntries = getDisplayEntries(report);
      const isExpanded = expandedReports.has(report.id);

      const reportToggleContent = (
        <Flex
          alignItems={{ default: 'alignItemsCenter' }}
          style={{ gap: '0.5rem' }}
        >
          <FlexItem>
            <strong>{report.title}</strong>
          </FlexItem>
          {report.project_key && (
            <FlexItem>
              <Label color="blue" isCompact>{report.project_key}</Label>
            </FlexItem>
          )}
          {report.report_period && (
            <FlexItem>
              <Label color="grey" isCompact>{report.report_period}</Label>
            </FlexItem>
          )}
          {isEditingReport && (
            <FlexItem>
              <Label color="orange" isCompact>Unsaved Changes</Label>
            </FlexItem>
          )}
          <FlexItem>
            <small style={{ color: '#6a6e73' }}>
              {report.created_at && format(new Date(report.created_at), 'MMM d, yyyy')}
            </small>
          </FlexItem>
        </Flex>
      );

      return (
        <Card
          key={report.id}
          style={{
            marginBottom: '1rem',
            border: isEditingReport ? '2px solid #0066cc' : undefined,
          }}
        >
          <CardBody style={{ paddingBottom: isExpanded ? undefined : 0 }}>
            <Flex
              justifyContent={{ default: 'justifyContentSpaceBetween' }}
              alignItems={{ default: 'alignItemsCenter' }}
              style={{ marginBottom: isExpanded ? '0.5rem' : 0 }}
            >
              <FlexItem style={{ flex: 1 }}>
                <ExpandableSection
                  toggleContent={reportToggleContent}
                  isExpanded={isExpanded}
                  onToggle={(_event, expanded) => {
                    setExpandedReports((prev) => {
                      const next = new Set(prev);
                      if (expanded) {
                        next.add(report.id);
                      } else {
                        next.delete(report.id);
                      }
                      return next;
                    });
                  }}
                >
                  <ReportEntryEditor
                    entries={displayEntries.length > 0 ? displayEntries : [{ text: '', private: false }]}
                    onChange={(entries) => handleEntryChange(report.id, entries)}
                    placeholder="Work item description with links..."
                    fields={fieldsData?.fields}
                  />

                  {isEditingReport && (
                    <Flex style={{ marginTop: '1rem', gap: '0.5rem' }}>
                      <FlexItem>
                        <Button
                          variant="primary"
                          onClick={() => handleSaveEdit(report.id)}
                          isLoading={updateMutation.isPending}
                        >
                          Save
                        </Button>
                      </FlexItem>
                      <FlexItem>
                        <Button
                          variant="link"
                          onClick={() => handleCancelEdit(report.id)}
                        >
                          Cancel
                        </Button>
                      </FlexItem>
                    </Flex>
                  )}

                  {report.referenced_tickets.length > 0 && (
                    <p style={{ marginTop: '1rem' }}>
                      <strong>Referenced Tickets:</strong>{' '}
                      {report.referenced_tickets.join(', ')}
                    </p>
                  )}
                </ExpandableSection>
              </FlexItem>
              <FlexItem>
                <Flex
                  alignItems={{ default: 'alignItemsCenter' }}
                  style={{ gap: '0.5rem' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <FlexItem>
                    <Tooltip content={visInfo.tooltip}>
                      <Button
                        variant="link"
                        onClick={() => handleToggleVisibility(report)}
                        isLoading={visibilityMutation.isPending}
                        style={{ color: visInfo.color, whiteSpace: 'nowrap', padding: '0.25rem 0.5rem' }}
                        icon={visInfo.icon}
                      >
                        {visInfo.label}
                      </Button>
                    </Tooltip>
                  </FlexItem>
                  <FlexItem>
                    <Button
                      variant="link"
                      isDanger
                      onClick={() => handleDelete(report.id)}
                    >
                      Delete
                    </Button>
                  </FlexItem>
                </Flex>
              </FlexItem>
            </Flex>
          </CardBody>
        </Card>
      );
    });
  };

  // ==========================================================================
  // Main Render
  // ==========================================================================

  return (
    <>
      <PageSection>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
          <FlexItem>
            <Content>
              <Title headingLevel="h1">Management Reports</Title>
            </Content>
          </FlexItem>
          <FlexItem>
            <Flex>
              {canViewTeams && teamsData?.teams.length ? (
                <FlexItem>
                  <FormSelect
                    value={selectedTeamId?.toString() || 'my'}
                    onChange={handleTeamChange}
                    aria-label="Select view"
                    style={{ minWidth: '200px' }}
                  >
                    <FormSelectOption value="my" label="My Reports" />
                    {teamsData.teams.map((team) => (
                      <FormSelectOption key={team.id} value={team.id.toString()} label={`Team: ${team.name}`} />
                    ))}
                  </FormSelect>
                </FlexItem>
              ) : null}
              {!selectedTeamId && (
                <FlexItem>
                  <Button
                    variant="primary"
                    icon={<PlusIcon />}
                    onClick={handleOpenCreateModal}
                  >
                    Create Report
                  </Button>
                </FlexItem>
              )}
            </Flex>
          </FlexItem>
        </Flex>
      </PageSection>

      <PageSection>
        {selectedTeamId ? (
          // Team view: show progress overview + table, or detail view
          selectedReportId ? renderReportDetailView() : (
            <>
              {renderProgressOverview()}
              {renderReportsTable()}
            </>
          )
        ) : (
          // Personal view: show personal reports
          renderPersonalReports()
        )}
      </PageSection>

      {/* Create Report Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        aria-labelledby="create-report-modal"
        variant="large"
      >
        <ModalHeader
          title="Create Management Report"
          labelId="create-report-modal"
        />
        <ModalBody>
          <Form>
            <FormGroup label="Title" isRequired fieldId="title">
              <TextInput
                isRequired
                id="title"
                value={newReportFormData.title}
                onChange={(_event, value) => setNewReportFormData({ ...newReportFormData, title: value })}
                placeholder="e.g., Week 4, January 2026"
              />
            </FormGroup>

            <FormGroup label="Project Key" fieldId="project-key">
              <TextInput
                id="project-key"
                value={newReportFormData.project_key || ''}
                onChange={(_event, value) => setNewReportFormData({ ...newReportFormData, project_key: value })}
                placeholder="e.g., APPENG"
              />
            </FormGroup>

            <FormGroup label="Report Period" fieldId="report-period">
              <TextInput
                id="report-period"
                value={newReportFormData.report_period || ''}
                onChange={(_event, value) => setNewReportFormData({ ...newReportFormData, report_period: value })}
                placeholder="e.g., Week 3, Jan 2026"
              />
            </FormGroup>

            <FormGroup
              label="Report Entries"
              isRequired
              fieldId="entries"
            >
              <p style={{ fontSize: '0.875rem', color: '#6a6e73', marginBottom: '0.5rem' }}>
                Add work items as separate entries. Click the eye/lock icon to toggle visibility to your manager.
              </p>
              <ReportEntryEditor
                entries={newReportEntries}
                onChange={setNewReportEntries}
                placeholder="Work item description with links..."
                fields={fieldsData?.fields}
              />
            </FormGroup>

            <FormGroup label="Referenced Tickets (comma-separated)" fieldId="tickets">
              <TextInput
                id="tickets"
                value={newReportFormData.referenced_tickets?.join(', ') || ''}
                onChange={(_event, value) =>
                  setNewReportFormData({
                    ...newReportFormData,
                    referenced_tickets: value.split(',').map((t) => t.trim()).filter(Boolean),
                  })
                }
                placeholder="e.g., PROJ-123, owner/repo#456"
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleCreateReport}
            isLoading={createMutation.isPending}
            isDisabled={!newReportFormData.title || !newReportEntries.some((e) => e.text.trim().length > 0)}
          >
            Create Report
          </Button>
          <Button variant="link" onClick={() => setIsModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>

      {/* Email Templates Modal */}
      <EmailTemplatesModal
        isOpen={emailTemplatesModalOpen}
        onClose={() => setEmailTemplatesModalOpen(false)}
      />
    </>
  );
}

export default ManagementReportsPage;

/**
 * Management Reports page - create and view management reports
 * Managers can view team members' reports and generate consolidated reports
 * Uses tabs: Consolidated Report (by field) and User Reports (by author)
 * Managers can edit consolidated reports with entry-by-entry editing
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
  ExpandableSection,
  Flex,
  FlexItem,
  Form,
  FormGroup,
  FormSelect,
  FormSelectOption,
  Label,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  PageSection,
  Spinner,
  Tab,
  Tabs,
  TabTitleText,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { PlusIcon, CopyIcon, UsersIcon, CubesIcon, LockIcon, EyeIcon, PencilAltIcon, SaveIcon, TimesIcon, FolderOpenIcon, TrashIcon, HistoryIcon } from '@patternfly/react-icons';
import { format } from 'date-fns';
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
  createConsolidatedSnapshot,
  deleteConsolidatedSnapshot,
} from '@/api/reports';
import { listTeams } from '@/api/teams';
import { useAuth } from '@/auth';
import { StyledMarkdown } from '@/components/StyledMarkdown';
import { ReportEntryEditor, reportEntriesToInputs } from '@/components/ReportEntryEditor';
import { ConsolidatedUserBlockEditor, type EditableEntry } from '@/components/ConsolidatedUserBlockEditor';
import type { 
  ManagementReportCreateRequest, 
  ManagementReport, 
  ReportEntryInput,
  ConsolidatedDraftContent,
  ConsolidatedDraftEntry,
  ConsolidatedDraft,
  ConsolidatedEntry,
} from '@/types';

// Configure marked for safe HTML output
marked.setOptions({
  breaks: true,
  gfm: true,
});

export function ManagementReportsPage() {
  const queryClient = useQueryClient();
  const { isManager, isAdmin } = useAuth();
  const canViewTeams = isManager || isAdmin;

  // Team selection state
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  // Default to showing consolidated preview for easy copy/paste
  const [showConsolidated, setShowConsolidated] = useState(true);
  const [copySuccess, setCopySuccess] = useState(false);
  
  // Tab state: 'consolidated' (by field) or 'user-reports' (by author)
  const [activeTab, setActiveTab] = useState<'consolidated' | 'user-reports'>('consolidated');
  
  // For backwards compatibility, derive useFieldView from activeTab
  const useFieldView = activeTab === 'consolidated';
  
  // Snapshot history panel state
  const [showHistory, setShowHistory] = useState(false);

  // Modal state (for creating new reports only)
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newReportEntries, setNewReportEntries] = useState<ReportEntryInput[]>([{ text: '', private: false }]);
  const [newReportFormData, setNewReportFormData] = useState<Omit<ManagementReportCreateRequest, 'content' | 'entries'>>({
    title: '',
    project_key: '',
    report_period: '',
    referenced_tickets: [],
  });

  // Inline editing state - tracks modified entries per report
  const [editedEntries, setEditedEntries] = useState<Record<number, ReportEntryInput[]>>({});

  // ==========================================================================
  // Draft Mode State (for manager editing of consolidated reports)
  // ==========================================================================
  
  // Whether we're in draft editing mode
  const [isDraftMode, setIsDraftMode] = useState(false);
  // Currently loaded draft ID (null if creating new draft)
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  // Draft title for new drafts
  const [draftTitle, setDraftTitle] = useState('');
  // Draft report period
  const [draftReportPeriod, setDraftReportPeriod] = useState('');
  // Edited draft content - tracks modifications to the draft
  const [editedDraftContent, setEditedDraftContent] = useState<ConsolidatedDraftContent | null>(null);
  // Track if draft has unsaved changes
  const [hasDraftChanges, setHasDraftChanges] = useState(false);
  // Load draft modal
  const [isLoadDraftModalOpen, setIsLoadDraftModalOpen] = useState(false);

  // ==========================================================================
  // Helper: Group draft entries by user for rendering
  // ==========================================================================
  
  /**
   * Groups draft entries by original_report_id and original_username for display.
   * Returns an array of "user blocks" that can be rendered with ConsolidatedUserBlockEditor.
   */
  const groupDraftEntriesByUser = useCallback((
    draftEntries: ConsolidatedDraftEntry[],
    originalUserEntries?: ConsolidatedEntry[]  // To get metadata like report_period, created_at
  ): Array<{
    reportId: number;
    username: string;
    reportPeriod: string | null;
    createdAt: string | null;
    entries: EditableEntry[];
  }> => {
    // Group entries by original_report_id
    const byReportId = new Map<number, ConsolidatedDraftEntry[]>();
    const managerAdded: ConsolidatedDraftEntry[] = [];
    
    for (const entry of draftEntries) {
      if (entry.original_report_id) {
        const existing = byReportId.get(entry.original_report_id) || [];
        existing.push(entry);
        byReportId.set(entry.original_report_id, existing);
      } else {
        managerAdded.push(entry);
      }
    }
    
    // Convert to user blocks
    const userBlocks: Array<{
      reportId: number;
      username: string;
      reportPeriod: string | null;
      createdAt: string | null;
      entries: EditableEntry[];
    }> = [];
    
    byReportId.forEach((entries, reportId) => {
      // Find original user entry metadata if available
      const originalEntry = originalUserEntries?.find(e => e.report_id === reportId);
      
      userBlocks.push({
        reportId,
        username: entries[0].original_username || 'Unknown',
        reportPeriod: originalEntry?.report_period || null,
        createdAt: originalEntry?.created_at || null,
        entries: entries.map((e, idx) => ({
          text: e.text,
          index: idx,
          isManagerAdded: e.is_manager_added,
        })),
      });
    });
    
    // Add manager-added entries as a separate block if any exist
    if (managerAdded.length > 0) {
      userBlocks.push({
        reportId: -1,  // Special ID for manager-added block
        username: 'Manager Notes',
        reportPeriod: null,
        createdAt: null,
        entries: managerAdded.map((e, idx) => ({
          text: e.text,
          index: idx,
          isManagerAdded: true,
        })),
      });
    }
    
    return userBlocks;
  }, []);

  // Fetch teams (for managers/admins)
  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => listTeams({ all_teams: true }),
    enabled: canViewTeams,
  });

  // Fetch management reports (either own or team-based)
  const { data: reportsData, isLoading } = useQuery({
    queryKey: ['managementReports', selectedTeamId],
    queryFn: () => 
      selectedTeamId 
        ? getTeamManagementReports(selectedTeamId, { limit: 100 })
        : listManagementReports({ limit: 50 }),
  });

  // Fetch consolidated report (field-based grouping)
  const { data: consolidatedData, isLoading: isConsolidatedLoading } = useQuery({
    queryKey: ['consolidatedReport', selectedTeamId],
    queryFn: () => getConsolidatedReport(selectedTeamId!, { limit: 100 }),
    enabled: !!selectedTeamId && useFieldView,
  });

  // Fetch drafts for the team (for loading existing drafts)
  const { data: draftsData, isLoading: isDraftsLoading } = useQuery({
    queryKey: ['consolidatedDrafts', selectedTeamId],
    queryFn: () => listConsolidatedDrafts(selectedTeamId!, { limit: 50 }),
    enabled: !!selectedTeamId && canViewTeams,
  });

  // Fetch snapshots for the team (report history)
  const { data: snapshotsData, isLoading: isSnapshotsLoading } = useQuery({
    queryKey: ['consolidatedSnapshots', selectedTeamId],
    queryFn: () => listConsolidatedSnapshots(selectedTeamId!, { limit: 50 }),
    enabled: !!selectedTeamId && canViewTeams,
  });

  // Create snapshot mutation
  const createSnapshotMutation = useMutation({
    mutationFn: (data: { report_period: string; label?: string }) =>
      createConsolidatedSnapshot(selectedTeamId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consolidatedSnapshots', selectedTeamId] });
    },
  });

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
      setSelectedDraftId(draft.id);
      setEditedDraftContent(draft.content);
      setDraftTitle(draft.title);
      setDraftReportPeriod(draft.report_period || '');
      setHasDraftChanges(false);
    },
  });

  // Update draft mutation
  const updateDraftMutation = useMutation({
    mutationFn: (data: { title?: string; report_period?: string; content?: ConsolidatedDraftContent }) =>
      updateConsolidatedDraft(selectedTeamId!, selectedDraftId!, data),
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
      // If we deleted the currently loaded draft, exit draft mode
      if (selectedDraftId) {
        handleExitDraftMode();
      }
    },
  });

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

  // Cancel inline editing - discard changes
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
      // Invalidate all related caches - management reports and consolidated report
      queryClient.invalidateQueries({ queryKey: ['managementReports'] });
      queryClient.invalidateQueries({ queryKey: ['consolidatedReport'] });
    },
  });

  const handleToggleVisibility = (report: ManagementReport) => {
    // Cycle through: null (inherit) -> true (visible) -> false (hidden) -> null
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
      return { icon: <EyeIcon />, tooltip: 'Visible to manager (override)', color: 'green' };
    } else if (report.visible_to_manager === false) {
      return { icon: <LockIcon />, tooltip: 'Hidden from manager (override)', color: 'red' };
    } else {
      return { icon: <EyeIcon />, tooltip: 'Using default visibility', color: 'grey' };
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

  // Group reports by author
  const reportsByAuthor = useMemo(() => {
    if (!reportsData?.reports) return {};
    
    const grouped: Record<string, ManagementReport[]> = {};
    reportsData.reports.forEach((report) => {
      if (!grouped[report.username]) {
        grouped[report.username] = [];
      }
      grouped[report.username].push(report);
    });
    return grouped;
  }, [reportsData]);

  // Generate consolidated markdown content
  const consolidatedMarkdown = useMemo(() => {
    // Use field-based structure if in field view and have consolidated data
    if (useFieldView && consolidatedData) {
      const lines: string[] = [];
      
      // Build field → project → entries structure
      consolidatedData.fields.forEach((field) => {
        lines.push(`# ${field.name}`);
        lines.push('');
        
        field.projects.forEach((project) => {
          lines.push(`## ${project.name}`);
          lines.push('');
          
          project.entries.forEach((userEntry) => {
            const displayName = userEntry.username.split('@')[0];
            lines.push(`### ${displayName}`);
            lines.push('');
            // Format individual entries as bullet points
            if (userEntry.entries && userEntry.entries.length > 0) {
              userEntry.entries.forEach((entry) => {
                lines.push(`- ${entry.text}`);
              });
            } else {
              // Fallback to combined content if no parsed entries
              lines.push(userEntry.content);
            }
            lines.push('');
          });
        });
      });
      
      // Add uncategorized entries
      if (consolidatedData.uncategorized.length > 0) {
        lines.push('# Other');
        lines.push('');
        
        consolidatedData.uncategorized.forEach((userEntry) => {
          const displayName = userEntry.username.split('@')[0];
          lines.push(`## ${displayName}`);
          lines.push('');
          // Format individual entries as bullet points
          if (userEntry.entries && userEntry.entries.length > 0) {
            userEntry.entries.forEach((entry) => {
              lines.push(`- ${entry.text}`);
            });
          } else {
            // Fallback to combined content if no parsed entries
            lines.push(userEntry.content);
          }
          lines.push('');
        });
      }
      
      return lines.join('\n');
    }
    
    // Fall back to author-based structure
    if (!reportsData?.reports.length) return '';
    
    const lines: string[] = [];
    
    // Group by author and get their latest report
    const latestByAuthor = new Map<string, ManagementReport>();
    reportsData.reports.forEach((report) => {
      const existing = latestByAuthor.get(report.username);
      if (!existing || (report.created_at && existing.created_at && report.created_at > existing.created_at)) {
        latestByAuthor.set(report.username, report);
      }
    });
    
    // Build consolidated content
    latestByAuthor.forEach((report, author) => {
      // Extract just the username part from email
      const displayName = author.split('@')[0];
      lines.push(`## ${displayName}`);
      lines.push('');
      lines.push(report.content);
      lines.push('');
    });
    
    return lines.join('\n');
  }, [reportsData, consolidatedData, useFieldView]);

  // Copy consolidated report as HTML for Gmail
  const handleCopyToClipboard = async () => {
    try {
      // Convert markdown to HTML
      const html = await marked.parse(consolidatedMarkdown);
      
      // Create styled HTML for Gmail
      const styledHtml = `
        <div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">
          ${html}
        </div>
      `;
      
      // Write to clipboard with both HTML and plain text
      const htmlBlob = new Blob([styledHtml], { type: 'text/html' });
      const textBlob = new Blob([consolidatedMarkdown], { type: 'text/plain' });
      
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
      // Fallback to plain text copy
      try {
        await navigator.clipboard.writeText(consolidatedMarkdown);
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 3000);
      } catch (fallbackErr) {
        console.error('Fallback copy also failed:', fallbackErr);
      }
    }
  };

  const handleTeamChange = (_event: React.FormEvent<HTMLSelectElement>, value: string) => {
    if (value === 'my') {
      setSelectedTeamId(null);
    } else {
      setSelectedTeamId(Number(value));
    }
    setShowConsolidated(false);
    // Exit draft mode when changing teams
    if (isDraftMode) {
      handleExitDraftMode();
    }
  };

  // ==========================================================================
  // Draft Mode Handlers
  // ==========================================================================

  // Convert consolidated report data to draft content format
  // Each user's individual entries are expanded into separate draft entries
  const convertConsolidatedToDraftContent = useCallback((): ConsolidatedDraftContent => {
    if (!consolidatedData) {
      return { format: 'consolidated_v1', fields: [], uncategorized: [] };
    }

    return {
      format: 'consolidated_v1',
      fields: consolidatedData.fields.map((field) => ({
        id: field.id,
        name: field.name,
        projects: field.projects.map((project) => ({
          id: project.id,
          name: project.name,
          // Expand each user's individual entries into separate draft entries
          entries: project.entries.flatMap((userEntry) =>
            (userEntry.entries || []).length > 0
              ? userEntry.entries.map((entry) => ({
                  text: entry.text,
                  original_report_id: userEntry.report_id,
                  original_username: userEntry.username,
                  is_manager_added: false,
                }))
              : [{
                  // Fallback if no parsed entries: use combined content
                  text: userEntry.content,
                  original_report_id: userEntry.report_id,
                  original_username: userEntry.username,
                  is_manager_added: false,
                }]
          ),
        })),
      })),
      uncategorized: consolidatedData.uncategorized.flatMap((userEntry) =>
        (userEntry.entries || []).length > 0
          ? userEntry.entries.map((entry) => ({
              text: entry.text,
              original_report_id: userEntry.report_id,
              original_username: userEntry.username,
              is_manager_added: false,
            }))
          : [{
              // Fallback if no parsed entries: use combined content
              text: userEntry.content,
              original_report_id: userEntry.report_id,
              original_username: userEntry.username,
              is_manager_added: false,
            }]
      ),
    };
  }, [consolidatedData]);

  // Start editing - create a new draft from current consolidated data
  const handleStartEditing = () => {
    const today = new Date();
    const defaultTitle = `Consolidated Report - ${format(today, 'MMM d, yyyy')}`;
    setDraftTitle(defaultTitle);
    setDraftReportPeriod('');
    setEditedDraftContent(convertConsolidatedToDraftContent());
    setSelectedDraftId(null);
    setIsDraftMode(true);
    setHasDraftChanges(false);
  };

  // Load an existing draft
  const handleLoadDraft = (draft: ConsolidatedDraft) => {
    setSelectedDraftId(draft.id);
    setDraftTitle(draft.title);
    setDraftReportPeriod(draft.report_period || '');
    setEditedDraftContent(draft.content);
    setIsDraftMode(true);
    setHasDraftChanges(false);
    setIsLoadDraftModalOpen(false);
  };

  // Exit draft mode
  const handleExitDraftMode = () => {
    if (hasDraftChanges && !confirm('You have unsaved changes. Are you sure you want to discard them?')) {
      return;
    }
    setIsDraftMode(false);
    setSelectedDraftId(null);
    setEditedDraftContent(null);
    setDraftTitle('');
    setDraftReportPeriod('');
    setHasDraftChanges(false);
  };

  // Save draft (update existing or create new)
  const handleSaveDraft = () => {
    if (!editedDraftContent || !draftTitle) return;

    if (selectedDraftId) {
      // Update existing draft
      updateDraftMutation.mutate({
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

  // Save as new draft (always creates a new draft, useful for versioning)
  const handleSaveAsNewDraft = () => {
    if (!editedDraftContent || !draftTitle) return;

    // Generate a versioned title if editing an existing draft
    let newTitle = draftTitle;
    if (selectedDraftId) {
      const timestamp = format(new Date(), 'MMM d, h:mm a');
      // Check if title already has a version indicator
      if (draftTitle.includes(' - v') || draftTitle.includes(' (')) {
        // Just add timestamp
        newTitle = `${draftTitle.split(' - v')[0].split(' (')[0]} - ${timestamp}`;
      } else {
        newTitle = `${draftTitle} - ${timestamp}`;
      }
    }

    // Create new draft (clear selected draft to create new)
    setSelectedDraftId(null);
    createDraftMutation.mutate({
      title: newTitle,
      report_period: draftReportPeriod || undefined,
      content: editedDraftContent,
    });
  };

  // Delete a draft
  const handleDeleteDraft = (draftId: number) => {
    if (confirm('Are you sure you want to delete this draft?')) {
      deleteDraftMutation.mutate(draftId);
    }
  };

  // Update entries for a specific user within a project (used by ConsolidatedUserBlockEditor)
  const handleUserEntriesChange = (fieldId: number, projectId: number, reportId: number, newEntries: EditableEntry[]) => {
    if (!editedDraftContent) return;

    const newContent = { ...editedDraftContent };
    const field = newContent.fields.find((f) => f.id === fieldId);
    if (field) {
      const project = field.projects.find((p) => p.id === projectId);
      if (project) {
        // Remove old entries for this user and add new ones
        const otherEntries = project.entries.filter(e => e.original_report_id !== reportId);
        const userEntry = consolidatedData?.fields
          .find(f => f.id === fieldId)?.projects
          .find(p => p.id === projectId)?.entries
          .find(e => e.report_id === reportId);
        
        const updatedUserEntries: ConsolidatedDraftEntry[] = newEntries.map(e => ({
          text: e.text,
          original_report_id: reportId,
          original_username: userEntry?.username || '',
          is_manager_added: e.isManagerAdded || e.index === -1,
        }));
        
        project.entries = [...otherEntries, ...updatedUserEntries];
        setEditedDraftContent(newContent);
        setHasDraftChanges(true);
      }
    }
  };

  // Update entries for uncategorized reports by user (used by ConsolidatedUserBlockEditor)
  const handleUncategorizedUserEntriesChange = (reportId: number, newEntries: EditableEntry[]) => {
    if (!editedDraftContent) return;

    const newContent = { ...editedDraftContent };
    // Remove old entries for this user and add new ones
    const otherEntries = newContent.uncategorized.filter(e => e.original_report_id !== reportId);
    const userEntry = consolidatedData?.uncategorized.find(e => e.report_id === reportId);
    
    const updatedUserEntries: ConsolidatedDraftEntry[] = newEntries.map(e => ({
      text: e.text,
      original_report_id: reportId,
      original_username: userEntry?.username || '',
      is_manager_added: e.isManagerAdded || e.index === -1,
    }));
    
    newContent.uncategorized = [...otherEntries, ...updatedUserEntries];
    setEditedDraftContent(newContent);
    setHasDraftChanges(true);
  };

  // Generate markdown from draft content for copy
  // Groups entries by user to avoid duplicate headers
  const draftToMarkdown = useCallback((): string => {
    if (!editedDraftContent) return '';

    const lines: string[] = [];

    // Helper to group entries by user
    const groupByUser = (entries: ConsolidatedDraftEntry[]): Map<string, ConsolidatedDraftEntry[]> => {
      const grouped = new Map<string, ConsolidatedDraftEntry[]>();
      entries.forEach((entry) => {
        // Use report_id as part of key to keep entries from same report together
        const key = entry.original_report_id 
          ? `${entry.original_username || 'Unknown'}::${entry.original_report_id}`
          : `manager-added::${entry.text.substring(0, 20)}`;
        const existing = grouped.get(key) || [];
        existing.push(entry);
        grouped.set(key, existing);
      });
      return grouped;
    };

    editedDraftContent.fields.forEach((field) => {
      lines.push(`# ${field.name}`);
      lines.push('');

      field.projects.forEach((project) => {
        lines.push(`## ${project.name}`);
        lines.push('');

        // Group entries by user
        const entriesByUser = groupByUser(project.entries);
        entriesByUser.forEach((userEntries) => {
          const firstEntry = userEntries[0];
          if (firstEntry.original_username) {
            const displayName = firstEntry.original_username.split('@')[0];
            lines.push(`### ${displayName}`);
            lines.push('');
          } else if (firstEntry.is_manager_added) {
            lines.push(`### Manager Notes`);
            lines.push('');
          }
          
          // Output each entry as a bullet point
          userEntries.forEach((entry) => {
            lines.push(`- ${entry.text}`);
          });
          lines.push('');
        });
      });
    });

    if (editedDraftContent.uncategorized.length > 0) {
      lines.push('# Other');
      lines.push('');

      // Group uncategorized entries by user
      const entriesByUser = groupByUser(editedDraftContent.uncategorized);
      entriesByUser.forEach((userEntries) => {
        const firstEntry = userEntries[0];
        if (firstEntry.original_username) {
          const displayName = firstEntry.original_username.split('@')[0];
          lines.push(`## ${displayName}`);
          lines.push('');
        } else if (firstEntry.is_manager_added) {
          lines.push(`## Manager Notes`);
          lines.push('');
        }
        
        // Output each entry as a bullet point
        userEntries.forEach((entry) => {
          lines.push(`- ${entry.text}`);
        });
        lines.push('');
      });
    }

    return lines.join('\n');
  }, [editedDraftContent]);

  // Copy draft to clipboard
  const handleCopyDraftToClipboard = async () => {
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
              <FlexItem>
                <Button
                  variant="primary"
                  icon={<PlusIcon />}
                  onClick={handleOpenCreateModal}
                >
                  Create Report
                </Button>
              </FlexItem>
            </Flex>
          </FlexItem>
        </Flex>
      </PageSection>

      {/* Consolidated Report Section - only show when viewing a team */}
      {selectedTeamId && (reportsData?.reports.length || consolidatedData?.total_entries) ? (
        <PageSection>
          <Card style={isDraftMode ? { border: '2px solid #0066cc' } : undefined}>
            <CardTitle>
              <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
                <FlexItem>
                  <Flex alignItems={{ default: 'alignItemsCenter' }}>
                    <FlexItem>
                      {useFieldView ? <CubesIcon style={{ marginRight: '0.5rem' }} /> : <UsersIcon style={{ marginRight: '0.5rem' }} />}
                    </FlexItem>
                    <FlexItem>
                      {isDraftMode ? (
                        <TextInput
                          value={draftTitle}
                          onChange={(_e, val) => { setDraftTitle(val); setHasDraftChanges(true); }}
                          aria-label="Draft title"
                          style={{ fontWeight: 'bold', fontSize: '1rem', minWidth: '300px' }}
                        />
                      ) : (
                        'Consolidated Team Report'
                      )}
                    </FlexItem>
                    <FlexItem>
                      <Label color={isDraftMode ? 'orange' : 'blue'} style={{ marginLeft: '0.5rem' }}>
                        {isDraftMode 
                          ? (hasDraftChanges ? 'Draft (Unsaved)' : (selectedDraftId ? 'Draft' : 'New Draft'))
                          : (useFieldView 
                              ? `${consolidatedData?.fields.length || 0} fields` 
                              : `${Object.keys(reportsByAuthor).length} members`)}
                      </Label>
                    </FlexItem>
                  </Flex>
                </FlexItem>
                <FlexItem>
                  <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ gap: '0.5rem' }}>
                    {!isDraftMode && (
                      <>
                        <FlexItem>
                          <Button
                            variant="primary"
                            icon={<CopyIcon />}
                            onClick={handleCopyToClipboard}
                          >
                            {copySuccess ? 'Copied!' : 'Copy for Gmail'}
                          </Button>
                        </FlexItem>
                        <FlexItem>
                          <Button
                            variant="secondary"
                            onClick={() => setShowConsolidated(!showConsolidated)}
                          >
                            {showConsolidated ? 'Hide' : 'Show'} Preview
                          </Button>
                        </FlexItem>
                        <FlexItem>
                          <Button
                            variant="plain"
                            icon={<HistoryIcon />}
                            onClick={() => setShowHistory(!showHistory)}
                          >
                            History
                          </Button>
                        </FlexItem>
                        {/* Draft editing controls */}
                        {canViewTeams && (
                          <>
                            <FlexItem>
                              <Button
                                variant="secondary"
                                icon={<PencilAltIcon />}
                                onClick={handleStartEditing}
                                isDisabled={!consolidatedData || consolidatedData.total_entries === 0}
                              >
                                Start Editing
                              </Button>
                            </FlexItem>
                            {draftsData && draftsData.drafts.length > 0 && (
                              <FlexItem>
                                <Button
                                  variant="secondary"
                                  icon={<FolderOpenIcon />}
                                  onClick={() => setIsLoadDraftModalOpen(true)}
                                >
                                  Load Draft ({draftsData.drafts.length})
                                </Button>
                              </FlexItem>
                            )}
                          </>
                        )}
                      </>
                    )}
                    {isDraftMode && (
                      <>
                        <FlexItem>
                          <TextInput
                            value={draftReportPeriod}
                            onChange={(_e, val) => { setDraftReportPeriod(val); setHasDraftChanges(true); }}
                            placeholder="Report period (e.g., Week 4, Jan 2026)"
                            aria-label="Report period"
                            style={{ minWidth: '200px' }}
                          />
                        </FlexItem>
                        <FlexItem>
                          <Button
                            variant="primary"
                            icon={<SaveIcon />}
                            onClick={handleSaveDraft}
                            isLoading={createDraftMutation.isPending || updateDraftMutation.isPending}
                            isDisabled={!draftTitle}
                          >
                            {selectedDraftId ? 'Save Draft' : 'Create Draft'}
                          </Button>
                        </FlexItem>
                        {selectedDraftId && (
                          <FlexItem>
                            <Button
                              variant="secondary"
                              icon={<PlusIcon />}
                              onClick={handleSaveAsNewDraft}
                              isLoading={createDraftMutation.isPending}
                              isDisabled={!draftTitle}
                            >
                              Save as New
                            </Button>
                          </FlexItem>
                        )}
                        <FlexItem>
                          <Button
                            variant="secondary"
                            icon={<CopyIcon />}
                            onClick={handleCopyDraftToClipboard}
                          >
                            {copySuccess ? 'Copied!' : 'Copy for Gmail'}
                          </Button>
                        </FlexItem>
                        <FlexItem>
                          <Button
                            variant="link"
                            icon={<TimesIcon />}
                            onClick={handleExitDraftMode}
                          >
                            {hasDraftChanges ? 'Discard' : 'Exit'}
                          </Button>
                        </FlexItem>
                      </>
                    )}
                  </Flex>
                </FlexItem>
              </Flex>
            </CardTitle>
            {showConsolidated && !isDraftMode && (
              <CardBody>
                {copySuccess && (
                  <Alert
                    variant="success"
                    isInline
                    title="Report copied to clipboard! You can now paste it in Gmail."
                    style={{ marginBottom: '1rem' }}
                  />
                )}
                {isConsolidatedLoading && useFieldView ? (
                  <Flex justifyContent={{ default: 'justifyContentCenter' }}>
                    <Spinner size="lg" />
                  </Flex>
                ) : (
                  <StyledMarkdown maxHeight="600px">{consolidatedMarkdown}</StyledMarkdown>
                )}
              </CardBody>
            )}
            {isDraftMode && (
              <CardBody>
                {copySuccess && (
                  <Alert
                    variant="success"
                    isInline
                    title="Report copied to clipboard! You can now paste it in Gmail."
                    style={{ marginBottom: '1rem' }}
                  />
                )}
                <StyledMarkdown maxHeight="600px">{draftToMarkdown()}</StyledMarkdown>
              </CardBody>
            )}
          </Card>

          {/* Snapshot History Panel */}
          {showHistory && !isDraftMode && (
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>
                <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
                  <FlexItem>
                    <HistoryIcon style={{ marginRight: '0.5rem' }} />
                    Report History
                    <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                      {snapshotsData?.total || 0} snapshot{(snapshotsData?.total || 0) !== 1 ? 's' : ''}
                    </Label>
                  </FlexItem>
                  <FlexItem>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        const period = consolidatedData?.report_period || 
                          `Week ${new Date().toISOString().slice(0, 10)}`;
                        const label = prompt('Enter a label for this snapshot (e.g., "Final Version"):');
                        if (label !== null) {
                          createSnapshotMutation.mutate({ 
                            report_period: period,
                            label: label || undefined 
                          });
                        }
                      }}
                      isLoading={createSnapshotMutation.isPending}
                    >
                      Save Manual Snapshot
                    </Button>
                  </FlexItem>
                </Flex>
              </CardTitle>
              <CardBody>
                {isSnapshotsLoading ? (
                  <Flex justifyContent={{ default: 'justifyContentCenter' }}>
                    <Spinner size="md" />
                  </Flex>
                ) : snapshotsData?.snapshots.length ? (
                  <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    {snapshotsData.snapshots.map((snapshot) => (
                      <Card 
                        key={snapshot.id} 
                        isPlain 
                        style={{ 
                          marginBottom: '0.5rem', 
                          padding: '0.75rem',
                          backgroundColor: snapshot.snapshot_type === 'auto' ? 'rgba(0, 0, 0, 0.02)' : 'rgba(0, 102, 204, 0.05)',
                          border: '1px solid #eee',
                          borderRadius: '4px',
                        }}
                      >
                        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
                          <FlexItem>
                            <Flex direction={{ default: 'column' }} style={{ gap: '0.25rem' }}>
                              <FlexItem>
                                <strong>
                                  {snapshot.label || (snapshot.snapshot_type === 'auto' ? 'Auto-saved' : 'Manual Save')}
                                </strong>
                                <Label 
                                  color={snapshot.snapshot_type === 'auto' ? 'grey' : 'blue'} 
                                  isCompact 
                                  style={{ marginLeft: '0.5rem' }}
                                >
                                  {snapshot.snapshot_type === 'auto' ? 'Auto' : 'Manual'}
                                </Label>
                              </FlexItem>
                              <FlexItem>
                                <small style={{ color: '#6a6e73' }}>
                                  {snapshot.report_period} • {format(new Date(snapshot.created_at), 'MMM d, yyyy h:mm a')}
                                </small>
                              </FlexItem>
                              <FlexItem>
                                <small style={{ color: '#6a6e73' }}>
                                  {snapshot.content.total_entries} entries across {snapshot.content.fields.length} fields
                                </small>
                              </FlexItem>
                            </Flex>
                          </FlexItem>
                          <FlexItem>
                            <Flex style={{ gap: '0.5rem' }}>
                              <FlexItem>
                                <Button
                                  variant="link"
                                  size="sm"
                                  onClick={() => {
                                    // View snapshot in a modal or expand
                                    alert(`Snapshot Details:\n\nPeriod: ${snapshot.report_period}\nType: ${snapshot.snapshot_type}\nEntries: ${snapshot.content.total_entries}\nFields: ${snapshot.content.fields.map(f => f.name).join(', ')}`);
                                  }}
                                >
                                  View
                                </Button>
                              </FlexItem>
                              {snapshot.snapshot_type === 'manual' && (
                                <FlexItem>
                                  <Button
                                    variant="plain"
                                    isDanger
                                    size="sm"
                                    onClick={() => {
                                      if (confirm('Delete this snapshot?')) {
                                        deleteSnapshotMutation.mutate(snapshot.id);
                                      }
                                    }}
                                    isLoading={deleteSnapshotMutation.isPending}
                                  >
                                    <TrashIcon />
                                  </Button>
                                </FlexItem>
                              )}
                            </Flex>
                          </FlexItem>
                        </Flex>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <p style={{ color: '#6a6e73' }}>
                    No snapshots yet. Snapshots are automatically saved when you first view the consolidated report.
                  </p>
                )}
              </CardBody>
            </Card>
          )}
        </PageSection>
      ) : null}

      {/* Tabs for switching between Consolidated and User Reports view */}
      {selectedTeamId && !isDraftMode && (
        <PageSection style={{ paddingTop: 0, paddingBottom: 0 }}>
          <Tabs 
            activeKey={activeTab} 
            onSelect={(_event, tabIndex) => setActiveTab(tabIndex as 'consolidated' | 'user-reports')}
            isFilled
            style={{ marginBottom: '1rem' }}
          >
            <Tab 
              eventKey="consolidated" 
              title={<TabTitleText><CubesIcon style={{ marginRight: '0.5rem' }} />Consolidated Report</TabTitleText>}
            />
            <Tab 
              eventKey="user-reports" 
              title={<TabTitleText><UsersIcon style={{ marginRight: '0.5rem' }} />User Reports</TabTitleText>}
            />
          </Tabs>
        </PageSection>
      )}

      <PageSection>
        {isLoading || (useFieldView && selectedTeamId && isConsolidatedLoading) ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : selectedTeamId && useFieldView && (consolidatedData || (isDraftMode && editedDraftContent)) ? (
          // Team view - group by field (Consolidated Report tab)
          <>
            {(isDraftMode && editedDraftContent ? editedDraftContent.fields : consolidatedData!.fields).map((field) => (
              <Card key={field.id} style={{ marginBottom: '1rem' }}>
                <CardTitle>
                  <Flex alignItems={{ default: 'alignItemsCenter' }}>
                    <FlexItem>
                      <CubesIcon style={{ marginRight: '0.5rem' }} />
                      {field.name}
                    </FlexItem>
                    <FlexItem>
                      <Label color="purple" style={{ marginLeft: '0.5rem' }}>
                        {field.projects.length} project{field.projects.length !== 1 ? 's' : ''}
                      </Label>
                    </FlexItem>
                  </Flex>
                </CardTitle>
                <CardBody>
                  {!isDraftMode && (consolidatedData?.fields.find(f => f.id === field.id)?.description) && (
                    <p style={{ marginBottom: '1rem' }}>{consolidatedData?.fields.find(f => f.id === field.id)?.description}</p>
                  )}
                  {field.projects.map((project) => (
                    <ExpandableSection
                      key={project.id}
                      toggleText={`${project.name} (${project.entries.length} entries)`}
                      style={{ marginBottom: '0.5rem' }}
                      isExpanded={isDraftMode}
                    >
                      <Card isPlain style={{ marginLeft: '1rem' }}>
                        <CardBody>
                          {!isDraftMode && (consolidatedData?.fields.find(f => f.id === field.id)?.projects.find(p => p.id === project.id)?.description) && (
                            <p style={{ marginBottom: '0.5rem', fontStyle: 'italic' }}>
                              {consolidatedData?.fields.find(f => f.id === field.id)?.projects.find(p => p.id === project.id)?.description}
                            </p>
                          )}
                          
                          {/* Render each user's entries using ConsolidatedUserBlockEditor */}
                          {isDraftMode ? (
                            // Draft mode: group flat entries by user for display
                            (() => {
                              const originalProject = consolidatedData?.fields.find(f => f.id === field.id)?.projects.find(p => p.id === project.id);
                              const draftProject = editedDraftContent?.fields.find(f => f.id === field.id)?.projects.find(p => p.id === project.id);
                              const userBlocks = groupDraftEntriesByUser(
                                draftProject?.entries || [],
                                originalProject?.entries
                              );
                              return userBlocks.map((userBlock) => (
                                <ConsolidatedUserBlockEditor
                                  key={userBlock.reportId}
                                  username={userBlock.username}
                                  reportPeriod={userBlock.reportPeriod}
                                  createdAt={userBlock.createdAt}
                                  reportId={userBlock.reportId}
                                  entries={userBlock.entries.map(e => ({ text: e.text, index: e.index }))}
                                  isEditing={true}
                                  onEntriesChange={(newEntries) => 
                                    handleUserEntriesChange(field.id, project.id, userBlock.reportId, newEntries)
                                  }
                                  placeholder="Work item description..."
                                />
                              ));
                            })()
                          ) : (
                            // Non-draft mode: use consolidatedData's user-grouped structure
                            consolidatedData?.fields.find(f => f.id === field.id)?.projects.find(p => p.id === project.id)?.entries.map((userEntry) => (
                              <ConsolidatedUserBlockEditor
                                key={userEntry.report_id}
                                username={userEntry.username}
                                reportPeriod={userEntry.report_period}
                                createdAt={userEntry.created_at}
                                reportId={userEntry.report_id}
                                entries={userEntry.entries || []}
                                isEditing={false}
                                onEntriesChange={() => {}}  // Not used in non-edit mode
                                placeholder="Work item description..."
                              />
                            ))
                          )}
                        </CardBody>
                      </Card>
                    </ExpandableSection>
                  ))}
                </CardBody>
              </Card>
            ))}
            
            {/* Uncategorized entries */}
            {((isDraftMode && editedDraftContent && editedDraftContent.uncategorized.length > 0) || 
              (!isDraftMode && consolidatedData && consolidatedData.uncategorized.length > 0)) && (
              <Card style={{ marginBottom: '1rem' }}>
                <CardTitle>
                  <Flex alignItems={{ default: 'alignItemsCenter' }}>
                    <FlexItem>Uncategorized</FlexItem>
                    <FlexItem>
                      <Label color="grey" style={{ marginLeft: '0.5rem' }}>
                        {isDraftMode 
                          ? editedDraftContent?.uncategorized.length 
                          : consolidatedData?.uncategorized.length} entries
                      </Label>
                    </FlexItem>
                  </Flex>
                </CardTitle>
                <CardBody>
                  {/* Render each user's uncategorized entries using ConsolidatedUserBlockEditor */}
                  {isDraftMode ? (
                    // Draft mode: group flat entries by user for display
                    (() => {
                      const userBlocks = groupDraftEntriesByUser(
                        editedDraftContent?.uncategorized || [],
                        consolidatedData?.uncategorized
                      );
                      return userBlocks.map((userBlock) => (
                        <ConsolidatedUserBlockEditor
                          key={userBlock.reportId}
                          username={userBlock.username}
                          reportPeriod={userBlock.reportPeriod}
                          createdAt={userBlock.createdAt}
                          reportId={userBlock.reportId}
                          entries={userBlock.entries.map(e => ({ text: e.text, index: e.index }))}
                          isEditing={true}
                          onEntriesChange={(newEntries) => 
                            handleUncategorizedUserEntriesChange(userBlock.reportId, newEntries)
                          }
                          placeholder="Work item description..."
                        />
                      ));
                    })()
                  ) : (
                    // Non-draft mode: use consolidatedData's user-grouped structure
                    consolidatedData?.uncategorized.map((userEntry) => (
                      <ConsolidatedUserBlockEditor
                        key={userEntry.report_id}
                        username={userEntry.username}
                        reportPeriod={userEntry.report_period}
                        createdAt={userEntry.created_at}
                        reportId={userEntry.report_id}
                        entries={userEntry.entries || []}
                        isEditing={false}
                        onEntriesChange={() => {}}  // Not used in non-edit mode
                        placeholder="Work item description..."
                      />
                    ))
                  )}
                </CardBody>
              </Card>
            )}
            
            {!isDraftMode && consolidatedData && consolidatedData.fields.length === 0 && consolidatedData.uncategorized.length === 0 && (
              <Card>
                <CardBody>
                  <p>No reports found. Configure fields and projects in the admin section to enable field-based grouping.</p>
                </CardBody>
              </Card>
            )}
          </>
        ) : reportsData?.reports.length ? (
          selectedTeamId ? (
            // Team view - group by author (original view)
            Object.entries(reportsByAuthor).map(([author, reports]) => (
              <Card key={author} style={{ marginBottom: '1rem' }}>
                <CardTitle>
                  <Flex alignItems={{ default: 'alignItemsCenter' }}>
                    <FlexItem>{author}</FlexItem>
                    <FlexItem>
                      <Label color="grey" style={{ marginLeft: '0.5rem' }}>
                        {reports.length} report{reports.length !== 1 ? 's' : ''}
                      </Label>
                    </FlexItem>
                  </Flex>
                </CardTitle>
                <CardBody>
                  {reports.map((report) => (
                    <ExpandableSection
                      key={report.id}
                      toggleText={`${report.title}${report.report_period ? ` - ${report.report_period}` : ''}`}
                      style={{ marginBottom: '0.5rem' }}
                    >
                      <Card isPlain>
                        <CardBody>
                          <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} style={{ marginBottom: '0.5rem' }}>
                            <FlexItem>
                              {report.project_key && (
                                <Label color="blue" style={{ marginRight: '0.5rem' }}>
                                  {report.project_key}
                                </Label>
                              )}
                              {report.report_period && (
                                <Label color="grey">
                                  {report.report_period}
                                </Label>
                              )}
                            </FlexItem>
                            <FlexItem>
                              <small>
                                {report.created_at && format(new Date(report.created_at), 'MMM d, yyyy')}
                              </small>
                            </FlexItem>
                          </Flex>
                          <StyledMarkdown maxHeight="300px">{report.content}</StyledMarkdown>
                          {report.referenced_tickets.length > 0 && (
                            <p style={{ marginTop: '1rem' }}>
                              <strong>Referenced Tickets:</strong>{' '}
                              {report.referenced_tickets.join(', ')}
                            </p>
                          )}
                        </CardBody>
                      </Card>
                    </ExpandableSection>
                  ))}
                </CardBody>
              </Card>
            ))
          ) : (
            // Personal view - flat list with inline editing
            reportsData.reports.map((report) => {
              const visInfo = getVisibilityInfo(report);
              const isEditing = hasChanges(report.id);
              const displayEntries = getDisplayEntries(report);
              
              return (
              <Card 
                key={report.id} 
                style={{ 
                  marginBottom: '1rem',
                  border: isEditing ? '2px solid #0066cc' : undefined,
                }}
              >
                <CardTitle>
                  <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
                    <FlexItem>
                      {report.title}
                      {report.project_key && (
                        <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                          {report.project_key}
                        </Label>
                      )}
                      {report.report_period && (
                        <Label color="grey" style={{ marginLeft: '0.5rem' }}>
                          {report.report_period}
                        </Label>
                      )}
                      {isEditing && (
                        <Label color="orange" style={{ marginLeft: '0.5rem' }}>
                          Unsaved Changes
                        </Label>
                      )}
                    </FlexItem>
                    <FlexItem>
                      <small>
                        {report.created_at && format(new Date(report.created_at), 'MMM d, yyyy')}
                      </small>
                      <Button
                        variant="plain"
                        aria-label={visInfo.tooltip}
                        title={visInfo.tooltip}
                        onClick={() => handleToggleVisibility(report)}
                        isLoading={visibilityMutation.isPending}
                        style={{ color: visInfo.color, marginLeft: '0.5rem' }}
                      >
                        {visInfo.icon}
                      </Button>
                      <Button
                        variant="link"
                        isDanger
                        onClick={() => handleDelete(report.id)}
                        style={{ marginLeft: '0.5rem' }}
                      >
                        Delete
                      </Button>
                    </FlexItem>
                  </Flex>
                </CardTitle>
                <CardBody>
                  {/* Inline editable entries */}
                  <ReportEntryEditor
                    entries={displayEntries.length > 0 ? displayEntries : [{ text: '', private: false }]}
                    onChange={(entries) => handleEntryChange(report.id, entries)}
                    placeholder="Work item description with links..."
                  />
                  
                  {/* Save/Cancel buttons when there are unsaved changes */}
                  {isEditing && (
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
                </CardBody>
              </Card>
              );
            })
          )
        ) : (
          <Card>
            <CardBody>
              <p>
                {selectedTeamId 
                  ? 'No management reports from team members yet.'
                  : 'No management reports yet. Click "Create Report" to add one.'}
              </p>
            </CardBody>
          </Card>
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

      {/* Load Draft Modal */}
      <Modal
        isOpen={isLoadDraftModalOpen}
        onClose={() => setIsLoadDraftModalOpen(false)}
        aria-labelledby="load-draft-modal"
        variant="medium"
      >
        <ModalHeader 
          title="Load Existing Draft" 
          labelId="load-draft-modal" 
        />
        <ModalBody>
          {isDraftsLoading ? (
            <Flex justifyContent={{ default: 'justifyContentCenter' }}>
              <Spinner size="lg" />
            </Flex>
          ) : draftsData?.drafts.length ? (
            <div style={{ maxHeight: '450px', overflowY: 'auto' }}>
              <p style={{ marginBottom: '1rem', color: '#6a6e73', fontSize: '0.875rem' }}>
                {draftsData.drafts.length} draft{draftsData.drafts.length !== 1 ? 's' : ''} available. 
                Click to load, or delete unwanted drafts.
              </p>
              {/* Sort drafts by updated_at or created_at (most recent first) */}
              {[...draftsData.drafts]
                .sort((a, b) => {
                  const dateA = a.updated_at || a.created_at || '';
                  const dateB = b.updated_at || b.created_at || '';
                  return dateB.localeCompare(dateA);
                })
                .map((draft) => {
                  // Check if this draft was recently modified (within last 24 hours)
                  const lastModified = draft.updated_at || draft.created_at;
                  const isRecent = lastModified && 
                    (new Date().getTime() - new Date(lastModified).getTime()) < 24 * 60 * 60 * 1000;
                  
                  // Count entries in the draft
                  const totalEntries = draft.content.fields.reduce(
                    (sum, field) => sum + field.projects.reduce(
                      (pSum, project) => pSum + project.entries.length, 0
                    ), 0
                  ) + (draft.content.uncategorized?.length || 0);

                  return (
                    <Card 
                      key={draft.id} 
                      isSelectable
                      isClickable
                      onClick={() => handleLoadDraft(draft)}
                      style={{ 
                        marginBottom: '0.75rem',
                        border: isRecent ? '1px solid #0066cc' : undefined,
                      }}
                    >
                      <CardBody style={{ padding: '1rem' }}>
                        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsFlexStart' }}>
                          <FlexItem style={{ flex: 1 }}>
                            <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ marginBottom: '0.5rem' }}>
                              <FlexItem>
                                <strong style={{ fontSize: '1rem' }}>{draft.title}</strong>
                              </FlexItem>
                              {isRecent && (
                                <FlexItem>
                                  <Label color="blue" isCompact style={{ marginLeft: '0.5rem' }}>
                                    Recent
                                  </Label>
                                </FlexItem>
                              )}
                              {draft.report_period && (
                                <FlexItem>
                                  <Label color="grey" isCompact style={{ marginLeft: '0.5rem' }}>
                                    {draft.report_period}
                                  </Label>
                                </FlexItem>
                              )}
                            </Flex>
                            
                            {/* Stats row */}
                            <Flex style={{ marginBottom: '0.5rem', gap: '1rem' }}>
                              <FlexItem>
                                <small style={{ color: '#6a6e73' }}>
                                  {draft.content.fields.length} field{draft.content.fields.length !== 1 ? 's' : ''}
                                </small>
                              </FlexItem>
                              <FlexItem>
                                <small style={{ color: '#6a6e73' }}>
                                  {totalEntries} entr{totalEntries !== 1 ? 'ies' : 'y'}
                                </small>
                              </FlexItem>
                            </Flex>
                            
                            {/* Dates row */}
                            <Flex direction={{ default: 'column' }} style={{ gap: '0.125rem' }}>
                              {draft.created_at && (
                                <FlexItem>
                                  <small style={{ color: '#6a6e73' }}>
                                    Created: {format(new Date(draft.created_at), 'MMM d, yyyy h:mm a')}
                                  </small>
                                </FlexItem>
                              )}
                              {draft.updated_at && draft.updated_at !== draft.created_at && (
                                <FlexItem>
                                  <small style={{ color: '#0066cc', fontWeight: 500 }}>
                                    Modified: {format(new Date(draft.updated_at), 'MMM d, yyyy h:mm a')}
                                  </small>
                                </FlexItem>
                              )}
                            </Flex>
                          </FlexItem>
                          <FlexItem>
                            <Button
                              variant="plain"
                              isDanger
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteDraft(draft.id);
                              }}
                              aria-label="Delete draft"
                              isLoading={deleteDraftMutation.isPending}
                            >
                              <TrashIcon />
                            </Button>
                          </FlexItem>
                        </Flex>
                      </CardBody>
                    </Card>
                  );
                })}
            </div>
          ) : (
            <p>No drafts found. Start editing to create one.</p>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="link" onClick={() => setIsLoadDraftModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default ManagementReportsPage;

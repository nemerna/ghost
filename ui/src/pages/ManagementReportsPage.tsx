/**
 * Management Reports page - create and view management reports
 * Managers can view team members' reports and generate consolidated reports
 * Supports both author-based and field-based grouping
 */

import { useState, useMemo } from 'react';
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
  Switch,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { PlusIcon, CopyIcon, UsersIcon, CubesIcon, LockIcon, EyeIcon } from '@patternfly/react-icons';
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
} from '@/api/reports';
import { listTeams } from '@/api/teams';
import { useAuth } from '@/auth';
import { StyledMarkdown } from '@/components/StyledMarkdown';
import { ReportEntryEditor, reportEntriesToInputs } from '@/components/ReportEntryEditor';
import type { ManagementReportCreateRequest, ManagementReport, ReportEntryInput } from '@/types';

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
  const [showConsolidated, setShowConsolidated] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  
  // View mode toggle: false = by author, true = by field
  const [useFieldView, setUseFieldView] = useState(false);

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
          
          project.entries.forEach((entry) => {
            const displayName = entry.username.split('@')[0];
            lines.push(`### ${displayName}`);
            lines.push('');
            lines.push(entry.content);
            lines.push('');
          });
        });
      });
      
      // Add uncategorized entries
      if (consolidatedData.uncategorized.length > 0) {
        lines.push('# Other');
        lines.push('');
        
        consolidatedData.uncategorized.forEach((entry) => {
          const displayName = entry.username.split('@')[0];
          lines.push(`## ${displayName}`);
          lines.push('');
          lines.push(entry.content);
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
          <Card>
            <CardTitle>
              <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
                <FlexItem>
                  <Flex alignItems={{ default: 'alignItemsCenter' }}>
                    <FlexItem>
                      {useFieldView ? <CubesIcon style={{ marginRight: '0.5rem' }} /> : <UsersIcon style={{ marginRight: '0.5rem' }} />}
                    </FlexItem>
                    <FlexItem>
                      Consolidated Team Report
                    </FlexItem>
                    <FlexItem>
                      <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                        {useFieldView 
                          ? `${consolidatedData?.fields.length || 0} fields` 
                          : `${Object.keys(reportsByAuthor).length} members`}
                      </Label>
                    </FlexItem>
                  </Flex>
                </FlexItem>
                <FlexItem>
                  <Flex alignItems={{ default: 'alignItemsCenter' }}>
                    <FlexItem style={{ marginRight: '1rem' }}>
                      <Switch
                        id="view-mode-toggle"
                        label={useFieldView ? "By Field" : "By Author"}
                        isChecked={useFieldView}
                        onChange={(_event, checked) => setUseFieldView(checked)}
                      />
                    </FlexItem>
                    <FlexItem>
                      <Button
                        variant="secondary"
                        onClick={() => setShowConsolidated(!showConsolidated)}
                      >
                        {showConsolidated ? 'Hide' : 'Show'} Consolidated View
                      </Button>
                    </FlexItem>
                    {showConsolidated && (
                      <FlexItem>
                        <Button
                          variant="primary"
                          icon={<CopyIcon />}
                          onClick={handleCopyToClipboard}
                        >
                          {copySuccess ? 'Copied!' : 'Copy for Gmail'}
                        </Button>
                      </FlexItem>
                    )}
                  </Flex>
                </FlexItem>
              </Flex>
            </CardTitle>
            {showConsolidated && (
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
          </Card>
        </PageSection>
      ) : null}

      <PageSection>
        {isLoading || (useFieldView && selectedTeamId && isConsolidatedLoading) ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : selectedTeamId && useFieldView && consolidatedData ? (
          // Team view - group by field (new field-based view)
          <>
            {consolidatedData.fields.map((field) => (
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
                  {field.description && <p style={{ marginBottom: '1rem' }}>{field.description}</p>}
                  {field.projects.map((project) => (
                    <ExpandableSection
                      key={project.id}
                      toggleText={`${project.name} (${project.entries.length} entries)`}
                      style={{ marginBottom: '0.5rem' }}
                    >
                      <Card isPlain style={{ marginLeft: '1rem' }}>
                        <CardBody>
                          {project.description && <p style={{ marginBottom: '0.5rem', fontStyle: 'italic' }}>{project.description}</p>}
                          {project.entries.map((entry) => (
                            <div key={entry.report_id} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #eee' }}>
                              <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} style={{ marginBottom: '0.5rem' }}>
                                <FlexItem>
                                  <strong>{entry.username.split('@')[0]}</strong>
                                  {entry.report_period && (
                                    <Label color="grey" style={{ marginLeft: '0.5rem' }}>
                                      {entry.report_period}
                                    </Label>
                                  )}
                                </FlexItem>
                                <FlexItem>
                                  <small>
                                    {entry.created_at && format(new Date(entry.created_at), 'MMM d, yyyy')}
                                  </small>
                                </FlexItem>
                              </Flex>
                              <StyledMarkdown maxHeight="200px">{entry.content}</StyledMarkdown>
                            </div>
                          ))}
                        </CardBody>
                      </Card>
                    </ExpandableSection>
                  ))}
                </CardBody>
              </Card>
            ))}
            
            {/* Uncategorized entries */}
            {consolidatedData.uncategorized.length > 0 && (
              <Card style={{ marginBottom: '1rem' }}>
                <CardTitle>
                  <Flex alignItems={{ default: 'alignItemsCenter' }}>
                    <FlexItem>Uncategorized</FlexItem>
                    <FlexItem>
                      <Label color="grey" style={{ marginLeft: '0.5rem' }}>
                        {consolidatedData.uncategorized.length} entries
                      </Label>
                    </FlexItem>
                  </Flex>
                </CardTitle>
                <CardBody>
                  {consolidatedData.uncategorized.map((entry) => (
                    <ExpandableSection
                      key={entry.report_id}
                      toggleText={`${entry.username.split('@')[0]} - ${entry.title}`}
                      style={{ marginBottom: '0.5rem' }}
                    >
                      <Card isPlain>
                        <CardBody>
                          <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} style={{ marginBottom: '0.5rem' }}>
                            <FlexItem>
                              {entry.report_period && (
                                <Label color="grey">{entry.report_period}</Label>
                              )}
                            </FlexItem>
                            <FlexItem>
                              <small>
                                {entry.created_at && format(new Date(entry.created_at), 'MMM d, yyyy')}
                              </small>
                            </FlexItem>
                          </Flex>
                          <StyledMarkdown maxHeight="300px">{entry.content}</StyledMarkdown>
                        </CardBody>
                      </Card>
                    </ExpandableSection>
                  ))}
                </CardBody>
              </Card>
            )}
            
            {consolidatedData.fields.length === 0 && consolidatedData.uncategorized.length === 0 && (
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
    </>
  );
}

export default ManagementReportsPage;

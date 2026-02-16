/**
 * Activities page - view and log activities
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  CardBody,
  Content,
  Form,
  FormGroup,
  FormHelperText,
  FormSelect,
  FormSelectOption,
  HelperText,
  HelperTextItem,
  Label,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  PageSection,
  Pagination,
  TextInput,
  Title,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
} from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr } from '@patternfly/react-table';
import { PlusIcon, TrashIcon, ExternalLinkAltIcon, LockIcon, EyeIcon } from '@patternfly/react-icons';
import { format } from 'date-fns';
import { getMyActivities, createActivity, deleteActivity, updateActivityVisibility } from '@/api/activities';
import type { Activity, ActivityCreateRequest, TicketSource } from '@/types';

/**
 * Generate a URL for a ticket based on its source and key.
 * GitHub: https://github.com/owner/repo/issues/number
 * Jira: Uses configured server URL from environment or falls back to null
 */
function getTicketUrl(activity: Activity): string | null {
  if (activity.ticket_source === 'github') {
    // GitHub format: owner/repo#number
    const match = activity.ticket_key.match(/^([^#]+)#(\d+)$/);
    if (match) {
      const [, repo, issueNumber] = match;
      return `https://github.com/${repo}/issues/${issueNumber}`;
    }
  } else if (activity.ticket_source === 'jira' && activity.project_key) {
    // Jira format: Try to use JIRA_SERVER_URL from window config or environment
    const jiraServerUrl = (window as unknown as { JIRA_SERVER_URL?: string }).JIRA_SERVER_URL 
      || import.meta.env.VITE_JIRA_SERVER_URL;
    if (jiraServerUrl) {
      return `${jiraServerUrl}/browse/${activity.ticket_key}`;
    }
  }
  return null;
}
const ticketSources: Array<{ value: TicketSource | ''; label: string }> = [
  { value: '', label: 'All sources' },
  { value: 'jira', label: 'Jira' },
  { value: 'github', label: 'GitHub' },
];

export function ActivitiesPage() {
  const queryClient = useQueryClient();

  // Pagination state
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  // Filter state
  const [projectFilter, setProjectFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState<TicketSource | ''>('');

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newActivity, setNewActivity] = useState<ActivityCreateRequest>({
    ticket_key: '',
    ticket_summary: '',
  });

  // Fetch activities
  const { data: activities, isLoading } = useQuery({
    queryKey: ['myActivities', page, perPage, projectFilter, sourceFilter],
    queryFn: () =>
      getMyActivities({
        limit: perPage,
        offset: (page - 1) * perPage,
        project_key: projectFilter || undefined,
        ticket_source: sourceFilter || undefined,
      }),
  });

  // Create activity mutation
  const createMutation = useMutation({
    mutationFn: createActivity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myActivities'] });
      queryClient.invalidateQueries({ queryKey: ['activitySummary'] });
      setIsModalOpen(false);
      setNewActivity({ ticket_key: '', ticket_summary: '' });
    },
  });

  // Delete activity mutation
  const deleteMutation = useMutation({
    mutationFn: deleteActivity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myActivities'] });
      queryClient.invalidateQueries({ queryKey: ['activitySummary'] });
    },
  });

  // Update visibility mutation
  const visibilityMutation = useMutation({
    mutationFn: ({ id, visible }: { id: number; visible: boolean | null }) =>
      updateActivityVisibility(id, visible),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myActivities'] });
    },
  });

  const handleToggleVisibility = (activity: Activity) => {
    // Cycle through: null (inherit) -> true (visible) -> false (hidden) -> null
    let newValue: boolean | null;
    if (activity.visible_to_manager === null) {
      newValue = true; // Explicitly visible
    } else if (activity.visible_to_manager === true) {
      newValue = false; // Explicitly hidden
    } else {
      newValue = null; // Back to inherit
    }
    visibilityMutation.mutate({ id: activity.id, visible: newValue });
  };

  const getVisibilityIcon = (activity: Activity) => {
    if (activity.visible_to_manager === true) {
      return { icon: <EyeIcon />, tooltip: 'Visible to manager (override)', color: 'green' };
    } else if (activity.visible_to_manager === false) {
      return { icon: <LockIcon />, tooltip: 'Hidden from manager (override)', color: 'red' };
    } else {
      return { icon: <EyeIcon />, tooltip: 'Using default visibility', color: 'grey' };
    }
  };

  const handleCreateActivity = () => {
    if (newActivity.ticket_key) {
      createMutation.mutate(newActivity);
    }
  };

  const handleDeleteActivity = (id: number) => {
    if (confirm('Are you sure you want to delete this activity?')) {
      deleteMutation.mutate(id);
    }
  };

  const columns = ['Source', 'Ticket', 'Summary', 'Project/Repo', 'Timestamp', 'Visibility', 'Actions'];

  return (
    <>
      <PageSection>
        <Content>
          <Title headingLevel="h1">My Activities</Title>
        </Content>
      </PageSection>

      <PageSection>
        <Card>
          <CardBody>
            <Toolbar>
              <ToolbarContent>
                <ToolbarItem>
                  <FormSelect
                    value={sourceFilter}
                    onChange={(_event, value) => setSourceFilter(value as TicketSource | '')}
                    aria-label="Filter by source"
                  >
                    {ticketSources.map((source) => (
                      <FormSelectOption key={source.value} value={source.value} label={source.label} />
                    ))}
                  </FormSelect>
                </ToolbarItem>
                <ToolbarItem>
                  <TextInput
                    placeholder="Filter by project/repo"
                    value={projectFilter}
                    onChange={(_event, value) => setProjectFilter(value)}
                    aria-label="Filter by project"
                  />
                </ToolbarItem>
                <ToolbarItem align={{ default: 'alignEnd' }}>
                  <Button
                    variant="primary"
                    icon={<PlusIcon />}
                    onClick={() => setIsModalOpen(true)}
                  >
                    Log Activity
                  </Button>
                </ToolbarItem>
              </ToolbarContent>
            </Toolbar>

            <Table aria-label="Activities table">
              <Thead>
                <Tr>
                  {columns.map((col) => (
                    <Th key={col}>{col}</Th>
                  ))}
                </Tr>
              </Thead>
              <Tbody>
                {isLoading ? (
                  <Tr>
                    <Td colSpan={columns.length}>Loading...</Td>
                  </Tr>
                ) : activities?.activities.length ? (
                  activities.activities.map((activity) => (
                    <Tr key={activity.id}>
                      <Td dataLabel="Source">
                        <Label color={activity.ticket_source === 'github' ? 'purple' : 'blue'}>
                          {activity.ticket_source === 'github' ? 'GitHub' : 'Jira'}
                        </Label>
                      </Td>
                      <Td dataLabel="Ticket">
                        {(() => {
                          const url = getTicketUrl(activity);
                          return url ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                            >
                              <strong>{activity.ticket_key}</strong>
                              <ExternalLinkAltIcon style={{ fontSize: '0.75em' }} />
                            </a>
                          ) : (
                            <strong>{activity.ticket_key}</strong>
                          );
                        })()}
                      </Td>
                      <Td dataLabel="Summary">
                        {activity.ticket_summary || '-'}
                      </Td>
                      <Td dataLabel="Project/Repo">
                        {activity.project_key || activity.github_repo || '-'}
                      </Td>
                      <Td dataLabel="Timestamp">
                        {format(new Date(activity.timestamp), 'MMM d, yyyy h:mm a')}
                      </Td>
                      <Td dataLabel="Visibility">
                        {(() => {
                          const vis = getVisibilityIcon(activity);
                          return (
                            <Button
                              variant="plain"
                              aria-label={vis.tooltip}
                              title={vis.tooltip}
                              onClick={() => handleToggleVisibility(activity)}
                              isLoading={visibilityMutation.isPending}
                              style={{ color: vis.color }}
                            >
                              {vis.icon}
                            </Button>
                          );
                        })()}
                      </Td>
                      <Td dataLabel="Actions">
                        <Button
                          variant="plain"
                          aria-label="Delete"
                          onClick={() => handleDeleteActivity(activity.id)}
                          isLoading={deleteMutation.isPending}
                        >
                          <TrashIcon />
                        </Button>
                      </Td>
                    </Tr>
                  ))
                ) : (
                  <Tr>
                    <Td colSpan={columns.length}>No activities found</Td>
                  </Tr>
                )}
              </Tbody>
            </Table>

            <Pagination
              itemCount={activities?.total || 0}
              perPage={perPage}
              page={page}
              onSetPage={(_event, newPage) => setPage(newPage)}
              onPerPageSelect={(_event, newPerPage) => {
                setPerPage(newPerPage);
                setPage(1);
              }}
              variant="bottom"
            />
          </CardBody>
        </Card>
      </PageSection>

      {/* Create Activity Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        aria-labelledby="log-activity-modal"
        variant="medium"
      >
        <ModalHeader title="Log Activity" labelId="log-activity-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Ticket Key" isRequired fieldId="ticket-key">
              <TextInput
                isRequired
                id="ticket-key"
                value={newActivity.ticket_key}
                onChange={(_event, value) =>
                  setNewActivity({ ...newActivity, ticket_key: value })
                }
                placeholder="e.g., PROJ-123 or owner/repo#42"
              />
              <FormHelperText>
                <HelperText>
                  <HelperTextItem>
                    Jira: PROJ-123 | GitHub: owner/repo#42
                  </HelperTextItem>
                </HelperText>
              </FormHelperText>
            </FormGroup>
            <FormGroup label="Summary" fieldId="ticket-summary">
              <TextInput
                id="ticket-summary"
                value={newActivity.ticket_summary || ''}
                onChange={(_event, value) =>
                  setNewActivity({ ...newActivity, ticket_summary: value })
                }
                placeholder="Brief description of the ticket"
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleCreateActivity}
            isLoading={createMutation.isPending}
            isDisabled={!newActivity.ticket_key}
          >
            Log Activity
          </Button>
          <Button variant="link" onClick={() => setIsModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default ActivitiesPage;

/**
 * Activities page - view and log activities
 */

import { useState, useCallback, useRef } from 'react';
import debounce from 'lodash/debounce';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Content,
  Skeleton,
  Form,
  FormGroup,
  FormHelperText,
  HelperText,
  HelperTextItem,
  Label,
  MenuToggle,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  PageSection,
  Pagination,
  Select,
  SelectList,
  SelectOption,
  TextInput,
  Title,
  Toolbar,
  ToolbarContent,
  ToolbarFilter,
  ToolbarGroup,
  ToolbarItem,
} from '@patternfly/react-core';
import type { MenuToggleElement } from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr, ActionsColumn, ThProps } from '@patternfly/react-table';
import { PlusIcon, ExternalLinkAltIcon, LockIcon, EyeIcon } from '@patternfly/react-icons';
import { format } from 'date-fns';
import { getMyActivities, createActivity, deleteActivity, updateActivityVisibility, updateActivity } from '@/api/activities';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';
import { useAuth } from '@/auth';
import { getTicketUrl } from '@/utils/tickets';
import type { Activity, ActivityCreateRequest, TicketSource } from '@/types';
const columns = [
  { label: 'Source',       modifier: 'fitContent' as const },
  { label: 'Ticket',       modifier: undefined              },
  { label: 'Summary',      modifier: undefined              },
  { label: 'Project/Repo', modifier: undefined              },
  { label: 'Timestamp',    modifier: 'fitContent' as const  },
  { label: 'Visibility',   modifier: 'fitContent' as const },
  { label: 'Actions',      modifier: 'fitContent' as const },
] as const;

const ticketSources: Array<{ value: TicketSource | ''; label: string }> = [
  { value: '', label: 'All sources' },
  { value: 'jira', label: 'Jira' },
  { value: 'github', label: 'GitHub' },
];

export function ActivitiesPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const jiraServerUrl = (user?.preferences?.jira_server_url as string) || '';

  // Pagination state
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  // Filter state — raw input drives UI; debounced value drives query
  const [projectFilter, setProjectFilter] = useState('');
  const [debouncedProjectFilter, setDebouncedProjectFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState<TicketSource | ''>('');
  const [isSourceSelectOpen, setIsSourceSelectOpen] = useState(false);

  const applyProjectFilter = useRef(
    debounce((value: string) => {
      setDebouncedProjectFilter(value);
      setPage(1);
    }, 350),
  ).current;

  const handleProjectFilterChange = useCallback(
    (_event: React.FormEvent, value: string) => {
      setProjectFilter(value);
      applyProjectFilter(value);
    },
    [applyProjectFilter],
  );

  // Create modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newActivity, setNewActivity] = useState<ActivityCreateRequest>({
    ticket_key: '',
    ticket_summary: '',
  });

  // Edit modal state
  const [editingActivity, setEditingActivity] = useState<Activity | null>(null);
  const [editTicketKey, setEditTicketKey] = useState('');
  const [editSummary, setEditSummary] = useState('');

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isBulkDeleteModalOpen, setIsBulkDeleteModalOpen] = useState(false);

  // Single-row delete confirmation
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const toggleSelectRow = (id: number, isSelected: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      isSelected ? next.add(id) : next.delete(id);
      return next;
    });
  };

  // Fetch activities
  const { data: activities, isLoading } = useQuery({
    queryKey: ['myActivities', page, perPage, debouncedProjectFilter, sourceFilter],
    queryFn: () =>
      getMyActivities({
        limit: perPage,
        offset: (page - 1) * perPage,
        ticket_source: sourceFilter || undefined,
        q: debouncedProjectFilter || undefined,
      }),
  });

  // Derived bulk-selection values — computed after activities are available
  const allIds = activities?.activities.map((a) => a.id) ?? [];
  const allSelected = allIds.length > 0 && allIds.every((id) => selectedIds.has(id));
  const someSelected = allIds.some((id) => selectedIds.has(id));
  const toggleSelectAll: ThProps['select'] = {
    onSelect: (_event, isSelected) => setSelectedIds(isSelected ? new Set(allIds) : new Set()),
    isSelected: allSelected,
  };

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
      setDeletingId(null);
    },
  });

  // Bulk delete mutation
  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: number[]) => Promise.all(ids.map(deleteActivity)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myActivities'] });
      queryClient.invalidateQueries({ queryKey: ['activitySummary'] });
      setSelectedIds(new Set());
      setIsBulkDeleteModalOpen(false);
    },
  });

  // Edit activity mutation
  const editMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { ticket_key?: string; ticket_summary?: string } }) =>
      updateActivity(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myActivities'] });
      setEditingActivity(null);
    },
  });

  const handleOpenEdit = (activity: Activity) => {
    setEditingActivity(activity);
    setEditTicketKey(activity.ticket_key);
    setEditSummary(activity.ticket_summary || '');
  };

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
      return { icon: <EyeIcon />, tooltip: 'Visible to manager (override)', color: 'var(--pf-t--global--icon--color--status--success--default)' };
    } else if (activity.visible_to_manager === false) {
      return { icon: <LockIcon />, tooltip: 'Hidden from manager (override)', color: 'var(--pf-t--global--icon--color--status--danger--default)' };
    } else {
      return { icon: <EyeIcon />, tooltip: 'Using default visibility', color: 'var(--pf-t--global--text--color--disabled)' };
    }
  };

  const handleCreateActivity = () => {
    if (newActivity.ticket_key) {
      createMutation.mutate(newActivity);
    }
  };

  const handleDeleteActivity = (id: number) => setDeletingId(id);


  const selectedSourceLabel = ticketSources.find((s) => s.value === sourceFilter)?.label;

  return (
    <>
      <PageSection>
        <Content>
          <Title headingLevel="h1">My Activities</Title>
        </Content>
      </PageSection>

      <PageSection>
          <Toolbar
            clearAllFilters={() => {
              setSourceFilter('');
              setProjectFilter('');
              setDebouncedProjectFilter('');
            }}
            clearFiltersButtonText="Clear filters"
          >
            <ToolbarContent>
              <ToolbarGroup variant="filter-group">
                {/* Source filter with active chip */}
                <ToolbarFilter
                  labels={sourceFilter ? [selectedSourceLabel ?? sourceFilter] : []}
                  deleteLabel={() => setSourceFilter('')}
                  categoryName="Source"
                >
                  <Select
                    isOpen={isSourceSelectOpen}
                    selected={sourceFilter || undefined}
                    onSelect={(_event, value) => {
                      setSourceFilter((value as TicketSource | '') ?? '');
                      setIsSourceSelectOpen(false);
                    }}
                    onOpenChange={setIsSourceSelectOpen}
                    toggle={(ref: React.Ref<MenuToggleElement>) => (
                      <MenuToggle
                        ref={ref}
                        onClick={() => setIsSourceSelectOpen((o) => !o)}
                        isExpanded={isSourceSelectOpen}
                      >
                        {selectedSourceLabel ?? 'All sources'}
                      </MenuToggle>
                    )}
                    shouldFocusToggleOnSelect
                  >
                    <SelectList>
                      {ticketSources.filter((s) => s.value !== '').map((source) => (
                        <SelectOption key={source.value} value={source.value}>
                          {source.label}
                        </SelectOption>
                      ))}
                    </SelectList>
                  </Select>
                </ToolbarFilter>

                {/* Project/repo text filter with active chip */}
                <ToolbarFilter
                  labels={debouncedProjectFilter ? [debouncedProjectFilter] : []}
                  deleteLabel={() => {
                    setProjectFilter('');
                    setDebouncedProjectFilter('');
                  }}
                  categoryName="Project/repo"
                >
                  <TextInput
                    placeholder="Filter by project/repo"
                    value={projectFilter}
                    onChange={handleProjectFilterChange}
                    aria-label="Filter by project"
                  />
                </ToolbarFilter>
              </ToolbarGroup>

              {/* Bulk delete */}
              {someSelected && (
                <ToolbarItem>
                  <Button variant="danger" onClick={() => setIsBulkDeleteModalOpen(true)}>
                    Delete ({selectedIds.size})
                  </Button>
                </ToolbarItem>
              )}

              <ToolbarItem align={{ default: 'alignEnd' }}>
                <Button variant="primary" icon={<PlusIcon />} onClick={() => setIsModalOpen(true)}>
                  Log Activity
                </Button>
              </ToolbarItem>
            </ToolbarContent>
          </Toolbar>

          <Table aria-label="Activities table">
            <Thead>
              <Tr>
                <Th select={toggleSelectAll} />
                {columns.map((col) => (
                  <Th key={col.label} modifier={col.modifier}>{col.label}</Th>
                ))}
              </Tr>
            </Thead>
            <Tbody>
              {isLoading ? (
                Array.from({ length: perPage }).map((_, i) => (
                  <Tr key={i}>
                    <Td />
                    {columns.map((col) => (
                      <Td key={col.label} dataLabel={col.label}>
                        <Skeleton />
                      </Td>
                    ))}
                  </Tr>
                ))
              ) : activities?.activities.length ? (
                activities.activities.map((activity, rowIndex) => (
                  <Tr key={activity.id} selected={selectedIds.has(activity.id)}>
                    <Td
                      select={{
                        rowIndex,
                        onSelect: (_event, isSelected) => toggleSelectRow(activity.id, isSelected),
                        isSelected: selectedIds.has(activity.id),
                      }}
                    />
                    <Td dataLabel="Source">
                      <Label color={activity.ticket_source === 'github' ? 'purple' : 'blue'}>
                        {activity.ticket_source === 'github' ? 'GitHub' : 'Jira'}
                      </Label>
                    </Td>
                    <Td dataLabel="Ticket">
                      {(() => {
                        const url = getTicketUrl(activity, jiraServerUrl);
                        return url ? (
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            {activity.ticket_key}
                            <ExternalLinkAltIcon style={{ fontSize: '0.75em' }} />
                          </a>
                        ) : activity.ticket_key;
                      })()}
                    </Td>
                    <Td dataLabel="Summary" modifier="breakWord">
                      {activity.ticket_summary || '-'}
                    </Td>
                    <Td dataLabel="Project/Repo">
                      {activity.project_key || activity.github_repo || '-'}
                    </Td>
                    <Td dataLabel="Timestamp" modifier="nowrap">
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
                    <Td isActionCell>
                      <ActionsColumn
                        items={[
                          {
                            title: 'Edit',
                            onClick: () => handleOpenEdit(activity),
                          },
                          {
                            title: 'Delete',
                            onClick: () => handleDeleteActivity(activity.id),
                          },
                        ]}
                      />
                    </Td>
                  </Tr>
                ))
              ) : (
                <Tr>
                  <Td colSpan={columns.length + 1}>No activities found</Td>
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

      {/* Edit Activity Modal */}
      <Modal
        isOpen={!!editingActivity}
        onClose={() => setEditingActivity(null)}
        aria-labelledby="edit-activity-modal"
        variant="medium"
      >
        <ModalHeader title="Edit Activity" labelId="edit-activity-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Ticket Key" isRequired fieldId="edit-ticket-key">
              <TextInput
                isRequired
                id="edit-ticket-key"
                value={editTicketKey}
                onChange={(_event, value) => setEditTicketKey(value)}
                placeholder="e.g., PROJ-123 or owner/repo#42"
              />
            </FormGroup>
            <FormGroup label="Summary" fieldId="edit-summary">
              <TextInput
                id="edit-summary"
                value={editSummary}
                onChange={(_event, value) => setEditSummary(value)}
                placeholder="Brief description of the ticket"
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            isLoading={editMutation.isPending}
            isDisabled={!editTicketKey}
            onClick={() =>
              editingActivity &&
              editMutation.mutate({
                id: editingActivity.id,
                data: { ticket_key: editTicketKey, ticket_summary: editSummary },
              })
            }
          >
            Save
          </Button>
          <Button variant="link" onClick={() => setEditingActivity(null)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>

      {/* Single-row delete confirmation */}
      <DeleteConfirmModal
        isOpen={deletingId !== null}
        onClose={() => setDeletingId(null)}
        onConfirm={() => deletingId !== null && deleteMutation.mutate(deletingId)}
        isLoading={deleteMutation.isPending}
      />

      {/* Bulk delete confirmation */}
      <DeleteConfirmModal
        isOpen={isBulkDeleteModalOpen}
        onClose={() => setIsBulkDeleteModalOpen(false)}
        onConfirm={() => bulkDeleteMutation.mutate(Array.from(selectedIds))}
        isLoading={bulkDeleteMutation.isPending}
        itemCount={selectedIds.size}
      />
    </>
  );
}

export default ActivitiesPage;

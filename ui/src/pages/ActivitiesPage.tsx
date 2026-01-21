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
  FormSelect,
  FormSelectOption,
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
import { PlusIcon, TrashIcon } from '@patternfly/react-icons';
import { format } from 'date-fns';
import { getMyActivities, createActivity, deleteActivity } from '@/api/activities';
import type { ActivityCreateRequest, ActionType } from '@/types';

const actionTypes: ActionType[] = ['view', 'create', 'update', 'comment', 'transition', 'link', 'other'];

export function ActivitiesPage() {
  const queryClient = useQueryClient();

  // Pagination state
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  // Filter state
  const [projectFilter, setProjectFilter] = useState('');
  const [actionTypeFilter, setActionTypeFilter] = useState('');

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newActivity, setNewActivity] = useState<ActivityCreateRequest>({
    ticket_key: '',
    ticket_summary: '',
    action_type: 'other',
  });

  // Fetch activities
  const { data: activities, isLoading } = useQuery({
    queryKey: ['myActivities', page, perPage, projectFilter, actionTypeFilter],
    queryFn: () =>
      getMyActivities({
        limit: perPage,
        offset: (page - 1) * perPage,
        project_key: projectFilter || undefined,
        action_type: actionTypeFilter || undefined,
      }),
  });

  // Create activity mutation
  const createMutation = useMutation({
    mutationFn: createActivity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myActivities'] });
      queryClient.invalidateQueries({ queryKey: ['activitySummary'] });
      setIsModalOpen(false);
      setNewActivity({ ticket_key: '', ticket_summary: '', action_type: 'other' });
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

  const columns = ['Ticket', 'Summary', 'Project', 'Action', 'Timestamp', 'Actions'];

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
                  <TextInput
                    placeholder="Filter by project"
                    value={projectFilter}
                    onChange={(_event, value) => setProjectFilter(value)}
                    aria-label="Filter by project"
                  />
                </ToolbarItem>
                <ToolbarItem>
                  <FormSelect
                    value={actionTypeFilter}
                    onChange={(_event, value) => setActionTypeFilter(value)}
                    aria-label="Filter by action type"
                  >
                    <FormSelectOption value="" label="All actions" />
                    {actionTypes.map((type) => (
                      <FormSelectOption key={type} value={type} label={type} />
                    ))}
                  </FormSelect>
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
                      <Td dataLabel="Ticket">
                        <strong>{activity.ticket_key}</strong>
                      </Td>
                      <Td dataLabel="Summary">
                        {activity.ticket_summary || '-'}
                      </Td>
                      <Td dataLabel="Project">
                        {activity.project_key || '-'}
                      </Td>
                      <Td dataLabel="Action">
                        {activity.action_type}
                      </Td>
                      <Td dataLabel="Timestamp">
                        {format(new Date(activity.timestamp), 'MMM d, yyyy h:mm a')}
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
                placeholder="e.g., PROJ-123"
              />
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
            <FormGroup label="Action Type" fieldId="action-type">
              <FormSelect
                id="action-type"
                value={newActivity.action_type}
                onChange={(_event, value) =>
                  setNewActivity({ ...newActivity, action_type: value as ActionType })
                }
              >
                {actionTypes.map((type) => (
                  <FormSelectOption key={type} value={type} label={type} />
                ))}
              </FormSelect>
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

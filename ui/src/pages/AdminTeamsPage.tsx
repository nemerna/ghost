/**
 * Admin Teams page - manage teams (admin only)
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  CardBody,
  CardTitle,
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
  PageSectionVariants,
  Spinner,
  TextArea,
  TextContent,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { PlusIcon, TrashIcon, UserPlusIcon } from '@patternfly/react-icons';
import { listTeams, createTeam, deleteTeam, getTeam, addTeamMember, removeTeamMember } from '@/api/teams';
import { listUsers } from '@/api/users';

export function AdminTeamsPage() {
  const queryClient = useQueryClient();

  // Modal state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isAddMemberModalOpen, setIsAddMemberModalOpen] = useState(false);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [newTeam, setNewTeam] = useState({ name: '', description: '', manager_id: '' });
  const [newMemberId, setNewMemberId] = useState('');

  // Fetch teams
  const { data: teamsData, isLoading } = useQuery({
    queryKey: ['teams', 'all'],
    queryFn: () => listTeams({ all_teams: true, limit: 100 }),
  });

  // Fetch users for manager selection
  const { data: usersData } = useQuery({
    queryKey: ['users', 'all'],
    queryFn: () => listUsers({ limit: 100 }),
  });

  // Fetch selected team details
  const { data: teamDetails } = useQuery({
    queryKey: ['team', selectedTeamId],
    queryFn: () => getTeam(selectedTeamId!),
    enabled: !!selectedTeamId,
  });

  // Create team mutation
  const createMutation = useMutation({
    mutationFn: createTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      setIsCreateModalOpen(false);
      setNewTeam({ name: '', description: '', manager_id: '' });
    },
  });

  // Delete team mutation
  const deleteMutation = useMutation({
    mutationFn: deleteTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
  });

  // Add member mutation
  const addMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      addTeamMember(teamId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team', selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      setIsAddMemberModalOpen(false);
      setNewMemberId('');
    },
  });

  // Remove member mutation
  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId, memberId }: { teamId: number; memberId: number }) =>
      removeTeamMember(teamId, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team', selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ['teams'] });
    },
  });

  const handleCreateTeam = () => {
    if (newTeam.name) {
      createMutation.mutate({
        name: newTeam.name,
        description: newTeam.description || undefined,
        manager_id: newTeam.manager_id ? Number(newTeam.manager_id) : undefined,
      });
    }
  };

  const handleDeleteTeam = (teamId: number, teamName: string) => {
    if (confirm(`Are you sure you want to delete team "${teamName}"?`)) {
      deleteMutation.mutate(teamId);
    }
  };

  const handleAddMember = () => {
    if (selectedTeamId && newMemberId) {
      addMemberMutation.mutate({
        teamId: selectedTeamId,
        userId: Number(newMemberId),
      });
    }
  };

  const handleRemoveMember = (memberId: number) => {
    if (selectedTeamId && confirm('Remove this member from the team?')) {
      removeMemberMutation.mutate({ teamId: selectedTeamId, memberId });
    }
  };

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
          <FlexItem>
            <TextContent>
              <Title headingLevel="h1">Team Management</Title>
            </TextContent>
          </FlexItem>
          <FlexItem>
            <Button
              variant="primary"
              icon={<PlusIcon />}
              onClick={() => setIsCreateModalOpen(true)}
            >
              Create Team
            </Button>
          </FlexItem>
        </Flex>
      </PageSection>

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : teamsData?.teams.length ? (
          teamsData.teams.map((team) => (
            <Card key={team.id} style={{ marginBottom: '1rem' }}>
              <CardTitle>
                <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
                  <FlexItem>
                    {team.name}
                    <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                      {team.member_count} members
                    </Label>
                  </FlexItem>
                  <FlexItem>
                    <Button
                      variant="secondary"
                      icon={<UserPlusIcon />}
                      onClick={() => {
                        setSelectedTeamId(team.id);
                        setIsAddMemberModalOpen(true);
                      }}
                      style={{ marginRight: '0.5rem' }}
                    >
                      Add Member
                    </Button>
                    <Button
                      variant="danger"
                      icon={<TrashIcon />}
                      onClick={() => handleDeleteTeam(team.id, team.name)}
                    >
                      Delete
                    </Button>
                  </FlexItem>
                </Flex>
              </CardTitle>
              <CardBody>
                <p><strong>Description:</strong> {team.description || 'No description'}</p>
                <p><strong>Manager:</strong> {team.manager_name || team.manager_email || 'Not assigned'}</p>
                
                <ExpandableSection
                  toggleText="View members"
                  onToggle={() => setSelectedTeamId(team.id)}
                >
                  {selectedTeamId === team.id && teamDetails?.members.length ? (
                    <ul style={{ marginTop: '1rem' }}>
                      {teamDetails.members.map((member) => (
                        <li key={member.id} style={{ marginBottom: '0.5rem' }}>
                          <Flex>
                            <FlexItem>
                              {member.display_name || member.email} ({member.role})
                            </FlexItem>
                            <FlexItem>
                              <Button
                                variant="link"
                                isDanger
                                onClick={() => handleRemoveMember(member.id)}
                              >
                                Remove
                              </Button>
                            </FlexItem>
                          </Flex>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>No members</p>
                  )}
                </ExpandableSection>
              </CardBody>
            </Card>
          ))
        ) : (
          <Card>
            <CardBody>
              <TextContent>
                <p>No teams yet. Click "Create Team" to add one.</p>
              </TextContent>
            </CardBody>
          </Card>
        )}
      </PageSection>

      {/* Create Team Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        aria-labelledby="create-team-modal"
        variant="medium"
      >
        <ModalHeader title="Create Team" labelId="create-team-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Team Name" isRequired fieldId="team-name">
              <TextInput
                isRequired
                id="team-name"
                value={newTeam.name}
                onChange={(_event, value) => setNewTeam({ ...newTeam, name: value })}
              />
            </FormGroup>
            <FormGroup label="Description" fieldId="description">
              <TextArea
                id="description"
                value={newTeam.description}
                onChange={(_event, value) => setNewTeam({ ...newTeam, description: value })}
                rows={3}
              />
            </FormGroup>
            <FormGroup label="Manager" fieldId="manager">
              <FormSelect
                id="manager"
                value={newTeam.manager_id}
                onChange={(_event, value) => setNewTeam({ ...newTeam, manager_id: value })}
              >
                <FormSelectOption value="" label="Select a manager (optional)" />
                {usersData?.users.map((user) => (
                  <FormSelectOption
                    key={user.id}
                    value={user.id.toString()}
                    label={`${user.display_name || user.email} (${user.role})`}
                  />
                ))}
              </FormSelect>
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleCreateTeam}
            isLoading={createMutation.isPending}
            isDisabled={!newTeam.name}
          >
            Create
          </Button>
          <Button variant="link" onClick={() => setIsCreateModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>

      {/* Add Member Modal */}
      <Modal
        isOpen={isAddMemberModalOpen}
        onClose={() => setIsAddMemberModalOpen(false)}
        aria-labelledby="add-member-modal"
        variant="small"
      >
        <ModalHeader title="Add Team Member" labelId="add-member-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Select User" isRequired fieldId="user-select">
              <FormSelect
                id="user-select"
                value={newMemberId}
                onChange={(_event, value) => setNewMemberId(value)}
              >
                <FormSelectOption value="" label="Select a user" />
                {usersData?.users.map((user) => (
                  <FormSelectOption
                    key={user.id}
                    value={user.id.toString()}
                    label={user.display_name || user.email}
                  />
                ))}
              </FormSelect>
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleAddMember}
            isLoading={addMemberMutation.isPending}
            isDisabled={!newMemberId}
          >
            Add
          </Button>
          <Button variant="link" onClick={() => setIsAddMemberModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default AdminTeamsPage;

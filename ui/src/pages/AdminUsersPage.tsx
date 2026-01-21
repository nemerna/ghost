/**
 * Admin Users page - manage users (admin only)
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
import { PencilAltIcon, TrashIcon } from '@patternfly/react-icons';
import { format } from 'date-fns';
import { listUsers, updateUser, deleteUser } from '@/api/users';
import type { User, UserRole } from '@/types';

const roles: UserRole[] = ['user', 'manager', 'admin'];

export function AdminUsersPage() {
  const queryClient = useQueryClient();

  // Pagination state
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  // Filter state
  const [searchFilter, setSearchFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');

  // Modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ display_name: '', role: '' });

  // Fetch users
  const { data: usersData, isLoading } = useQuery({
    queryKey: ['users', page, perPage, searchFilter, roleFilter],
    queryFn: () =>
      listUsers({
        limit: perPage,
        offset: (page - 1) * perPage,
        search: searchFilter || undefined,
        role: roleFilter || undefined,
      }),
  });

  // Update user mutation
  const updateMutation = useMutation({
    mutationFn: ({ userId, data }: { userId: number; data: { display_name?: string; role?: string } }) =>
      updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsEditModalOpen(false);
      setEditingUser(null);
    },
  });

  // Delete user mutation
  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setEditForm({
      display_name: user.display_name || '',
      role: user.role,
    });
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = () => {
    if (editingUser) {
      updateMutation.mutate({
        userId: editingUser.id,
        data: editForm,
      });
    }
  };

  const handleDelete = (user: User) => {
    if (confirm(`Are you sure you want to delete user ${user.email}?`)) {
      deleteMutation.mutate(user.id);
    }
  };

  const columns = ['Email', 'Display Name', 'Role', 'First Seen', 'Last Seen', 'Actions'];

  return (
    <>
      <PageSection>
        <Content>
          <Title headingLevel="h1">User Management</Title>
        </Content>
      </PageSection>

      <PageSection>
        <Card>
          <CardBody>
            <Toolbar>
              <ToolbarContent>
                <ToolbarItem>
                  <TextInput
                    placeholder="Search by email or name"
                    value={searchFilter}
                    onChange={(_event, value) => setSearchFilter(value)}
                    aria-label="Search users"
                  />
                </ToolbarItem>
                <ToolbarItem>
                  <FormSelect
                    value={roleFilter}
                    onChange={(_event, value) => setRoleFilter(value)}
                    aria-label="Filter by role"
                  >
                    <FormSelectOption value="" label="All roles" />
                    {roles.map((role) => (
                      <FormSelectOption key={role} value={role} label={role} />
                    ))}
                  </FormSelect>
                </ToolbarItem>
              </ToolbarContent>
            </Toolbar>

            <Table aria-label="Users table">
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
                ) : usersData?.users.length ? (
                  usersData.users.map((user) => (
                    <Tr key={user.id}>
                      <Td dataLabel="Email">{user.email}</Td>
                      <Td dataLabel="Display Name">{user.display_name || '-'}</Td>
                      <Td dataLabel="Role">{user.role}</Td>
                      <Td dataLabel="First Seen">
                        {user.first_seen ? format(new Date(user.first_seen), 'MMM d, yyyy') : '-'}
                      </Td>
                      <Td dataLabel="Last Seen">
                        {user.last_seen ? format(new Date(user.last_seen), 'MMM d, yyyy') : '-'}
                      </Td>
                      <Td dataLabel="Actions">
                        <Button
                          variant="plain"
                          aria-label="Edit"
                          onClick={() => handleEdit(user)}
                        >
                          <PencilAltIcon />
                        </Button>
                        <Button
                          variant="plain"
                          aria-label="Delete"
                          onClick={() => handleDelete(user)}
                        >
                          <TrashIcon />
                        </Button>
                      </Td>
                    </Tr>
                  ))
                ) : (
                  <Tr>
                    <Td colSpan={columns.length}>No users found</Td>
                  </Tr>
                )}
              </Tbody>
            </Table>

            <Pagination
              itemCount={usersData?.total || 0}
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

      {/* Edit User Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        aria-labelledby="edit-user-modal"
        variant="medium"
      >
        <ModalHeader title="Edit User" labelId="edit-user-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Email" fieldId="email">
              <TextInput
                id="email"
                value={editingUser?.email || ''}
                isDisabled
              />
            </FormGroup>
            <FormGroup label="Display Name" fieldId="display-name">
              <TextInput
                id="display-name"
                value={editForm.display_name}
                onChange={(_event, value) => setEditForm({ ...editForm, display_name: value })}
              />
            </FormGroup>
            <FormGroup label="Role" fieldId="role">
              <FormSelect
                id="role"
                value={editForm.role}
                onChange={(_event, value) => setEditForm({ ...editForm, role: value })}
              >
                {roles.map((role) => (
                  <FormSelectOption key={role} value={role} label={role} />
                ))}
              </FormSelect>
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleSaveEdit}
            isLoading={updateMutation.isPending}
          >
            Save
          </Button>
          <Button variant="link" onClick={() => setIsEditModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default AdminUsersPage;

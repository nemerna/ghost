import { useCallback, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Content,
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
  Pagination,
  Select,
  SelectList,
  SelectOption,
  Skeleton,
  TextInput,
  Title,
  Toolbar,
  ToolbarContent,
  ToolbarFilter,
  ToolbarGroup,
} from '@patternfly/react-core';
import type { MenuToggleElement } from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr, ActionsColumn } from '@patternfly/react-table';
import { format } from 'date-fns';
import debounce from 'lodash/debounce';
import { listUsers, updateUser, deleteUser } from '@/api/users';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';
import { ROLE_COLORS, ROLE_LABELS } from '@/utils/colors';
import type { User, UserRole } from '@/types';

const roles: UserRole[] = ['admin', 'manager', 'user'];

export function AdminUsersPage() {
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);

  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [isRoleSelectOpen, setIsRoleSelectOpen] = useState(false);

  const [deletingUser, setDeletingUser] = useState<User | null>(null);

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ display_name: '', role: '' });

  const applySearchFilter = useRef(
    debounce((value: string) => {
      setDebouncedSearch(value);
      setPage(1);
    }, 350),
  ).current;

  const handleSearchChange = useCallback(
    (_event: React.FormEvent, value: string) => {
      setSearchInput(value);
      applySearchFilter(value);
    },
    [applySearchFilter],
  );

  const { data: usersData, isLoading } = useQuery({
    queryKey: ['users', page, perPage, debouncedSearch, roleFilter],
    queryFn: () =>
      listUsers({
        limit: perPage,
        offset: (page - 1) * perPage,
        search: debouncedSearch || undefined,
        role: roleFilter || undefined,
      }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, data }: { userId: number; data: { display_name?: string; role?: string } }) =>
      updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setIsEditModalOpen(false);
      setEditingUser(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setDeletingUser(null);
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

  const handleDelete = (user: User) => setDeletingUser(user);

  const columns = ['Email', 'Display Name', 'Role', 'First Seen', 'Last Seen'];

  return (
    <>
      <PageSection>
        <Content>
          <Title headingLevel="h1">User Management</Title>
        </Content>
      </PageSection>

      <PageSection>
          <Toolbar
            clearAllFilters={() => {
              setSearchInput('');
              setDebouncedSearch('');
              applySearchFilter.cancel();
              setRoleFilter('');
            }}
            clearFiltersButtonText="Clear filters"
          >
            <ToolbarContent>
              <ToolbarGroup variant="filter-group">
                <ToolbarFilter
                  labels={debouncedSearch ? [debouncedSearch] : []}
                  deleteLabel={() => { setSearchInput(''); setDebouncedSearch(''); applySearchFilter.cancel(); }}
                  categoryName="Search"
                >
                  <TextInput
                    placeholder="Search by email or name"
                    value={searchInput}
                    onChange={handleSearchChange}
                    aria-label="Search users"
                  />
                </ToolbarFilter>

                <ToolbarFilter
                  labels={roleFilter ? [roleFilter] : []}
                  deleteLabel={() => setRoleFilter('')}
                  categoryName="Role"
                >
                  <Select
                    isOpen={isRoleSelectOpen}
                    selected={roleFilter || undefined}
                    onSelect={(_event, value) => {
                      setRoleFilter((value as UserRole | '') ?? '');
                      setIsRoleSelectOpen(false);
                      setPage(1);
                    }}
                    onOpenChange={setIsRoleSelectOpen}
                    toggle={(ref: React.Ref<MenuToggleElement>) => (
                      <MenuToggle
                        ref={ref}
                        onClick={() => setIsRoleSelectOpen((o) => !o)}
                        isExpanded={isRoleSelectOpen}
                      >
                        {roleFilter || 'All roles'}
                      </MenuToggle>
                    )}
                    shouldFocusToggleOnSelect
                  >
                    <SelectList>
                      {roles.map((role) => (
                        <SelectOption key={role} value={role}>
                          {role}
                        </SelectOption>
                      ))}
                    </SelectList>
                  </Select>
                </ToolbarFilter>
              </ToolbarGroup>
            </ToolbarContent>
          </Toolbar>

          <Table aria-label="Users table">
            <Thead>
              <Tr>
                {columns.map((col) => (
                  <Th key={col}>{col}</Th>
                ))}
                <Th screenReaderText="Actions" />
              </Tr>
            </Thead>
            <Tbody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <Tr key={i}>
                    <Td dataLabel="Email"><Skeleton width="60%" /></Td>
                    <Td dataLabel="Display Name"><Skeleton width="45%" /></Td>
                    <Td dataLabel="Role"><Skeleton width="30%" /></Td>
                    <Td dataLabel="First Seen"><Skeleton width="50%" /></Td>
                    <Td dataLabel="Last Seen"><Skeleton width="50%" /></Td>
                    <Td />
                  </Tr>
                ))
              ) : usersData?.users.length ? (
                usersData.users.map((user) => (
                  <Tr key={user.id}>
                    <Td dataLabel="Email">{user.email}</Td>
                    <Td dataLabel="Display Name">{user.display_name || '-'}</Td>
                    <Td dataLabel="Role">
                      <Label color={ROLE_COLORS[user.role]} isCompact>{ROLE_LABELS[user.role]}</Label>
                    </Td>
                    <Td dataLabel="First Seen">
                      {user.first_seen ? format(new Date(user.first_seen), 'MMM d, yyyy') : '-'}
                    </Td>
                    <Td dataLabel="Last Seen">
                      {user.last_seen ? format(new Date(user.last_seen), 'MMM d, yyyy') : '-'}
                    </Td>
                    <Td isActionCell>
                      <ActionsColumn
                        items={[
                          {
                            title: 'Edit',
                            onClick: () => handleEdit(user),
                          },
                          { isSeparator: true },
                          {
                            title: 'Delete',
                            onClick: () => handleDelete(user),
                          },
                        ]}
                      />
                    </Td>
                  </Tr>
                ))
              ) : (
                <Tr>
                  <Td colSpan={columns.length + 1}>No users found</Td>
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
      </PageSection>

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

      <DeleteConfirmModal
        isOpen={deletingUser !== null}
        onClose={() => setDeletingUser(null)}
        onConfirm={() => {
          if (deletingUser) {
            deleteMutation.mutate(deletingUser.id);
          }
        }}
        isLoading={deleteMutation.isPending}
        title="Delete user?"
        message={`Are you sure you want to delete user ${deletingUser?.email}? This action cannot be undone.`}
      />
    </>
  );
}

export default AdminUsersPage;

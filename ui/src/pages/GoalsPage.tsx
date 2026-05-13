/**
 * Goals page — team and individual goal tracking with alignment visibility,
 * team-wide goal health summary, and ticket activity from report entries.
 *
 * Engineers: own individual goals + team goals.
 * Managers/admins: all team goals + individual goals per member + ticket activity.
 */

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  CardBody,
  Content,
  Drawer,
  DrawerContent,
  DrawerContentBody,
  DrawerHead,
  DrawerPanelBody,
  DrawerPanelContent,
  Divider,
  EmptyState,
  EmptyStateBody,
  ExpandableSection,
  Flex,
  FlexItem,
  Form,
  FormGroup,
  FormSelect,
  FormSelectOption,
  Grid,
  GridItem,
  Label,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  PageSection,
  Spinner,
  TextArea,
  TextInput,
  Title,
  Tooltip,
} from '@patternfly/react-core';
import {
  ExpandableRowContent,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from '@patternfly/react-table';
import {
  BullseyeIcon,
  CheckCircleIcon,
  PencilAltIcon,
  PlusIcon,
  TagIcon,
  TimesCircleIcon,
  TrashIcon,
} from '@patternfly/react-icons';
import t_global_text_color_subtle from '@patternfly/react-tokens/dist/esm/t_global_text_color_subtle';
import { useAuth } from '@/auth';
import { listGoals, createGoal, updateGoal, deleteGoal, listGoalLinks, listGoalNotes, createGoalNote, deleteGoalNote } from '@/api/goals';
import { listTeams } from '@/api/teams';
import { getTicketActivity } from '@/api/activity';
import type { Goal, GoalEntryLink, GoalHorizon, GoalNote, GoalScope, GoalStatus, MemberTicketActivity } from '@/types';
import { InlineMarkdown } from '@/components/StyledMarkdown';
import { NONSTATUS_COLORS } from '@/utils/colors';

// =============================================================================
// Helpers
// =============================================================================

/** Compute a default ISO due-date string from a horizon (mirrors backend logic). */
function defaultDueDateForHorizon(horizon: GoalHorizon): string | undefined {
  const now = new Date();
  if (horizon === 'sprint') {
    const d = new Date(now);
    d.setDate(d.getDate() + 14);
    return d.toISOString().slice(0, 10);
  }
  if (horizon === 'quarter') {
    const m = now.getMonth(); // 0-indexed
    const y = now.getFullYear();
    if (m < 3) return `${y}-03-31`;
    if (m < 6) return `${y}-06-30`;
    if (m < 9) return `${y}-09-30`;
    return `${y}-12-31`;
  }
  return undefined; // ongoing
}

function formatDueDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function isDueSoon(iso: string | null | undefined): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  const now = new Date();
  const diff = d.getTime() - now.getTime();
  return diff >= 0 && diff < 7 * 24 * 60 * 60 * 1000;
}

function isOverdue(iso: string | null | undefined): boolean {
  if (!iso) return false;
  return new Date(iso).getTime() < new Date().getTime();
}

// =============================================================================
// Constants
// =============================================================================

const HORIZON_LABELS: Record<GoalHorizon, string> = {
  sprint: 'Sprint',
  quarter: 'Quarter',
  ongoing: 'Ongoing',
};

const HORIZON_COLORS: Record<GoalHorizon, 'blue' | 'purple' | 'grey'> = {
  sprint: 'blue',
  quarter: 'purple',
  ongoing: 'grey',
};

const STATUS_LABELS: Record<GoalStatus, string> = {
  active: 'Active',
  completed: 'Completed',
  dropped: 'Dropped',
};

const STATUS_COLORS: Record<GoalStatus, 'green' | 'blue' | 'grey'> = {
  active: 'green',
  completed: 'blue',
  dropped: 'grey',
};

// =============================================================================
// Alignment Bar
// =============================================================================

interface AlignmentBarProps {
  count: number;
  max: number;
  softMax?: number;
}

function AlignmentBar({ count, max, softMax }: AlignmentBarProps) {
  const effectiveMax = max > 0 ? max : (softMax ?? 10);
  const pct = Math.min(100, Math.round((count / effectiveMax) * 100));
  const color =
    pct >= 60
      ? 'var(--pf-t--global--color--status--success--default)'
      : pct >= 25
      ? 'var(--pf-t--global--color--status--warning--default)'
      : 'var(--pf-t--global--color--status--danger--default)';

  return (
    <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
      <FlexItem>
        <div
          style={{
            width: '56px',
            height: '5px',
            background: 'var(--pf-t--global--border--color--default)',
            borderRadius: '3px',
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: '100%',
              background: count === 0 ? 'var(--pf-t--global--border--color--default)' : color,
              borderRadius: '3px',
              transition: 'width 0.3s',
            }}
          />
        </div>
      </FlexItem>
      <FlexItem>
        <span style={{ fontSize: '0.8rem', color: t_global_text_color_subtle.var }}>
          {count} {count === 1 ? 'entry' : 'entries'}
        </span>
      </FlexItem>
    </Flex>
  );
}

// =============================================================================
// Member Avatar
// =============================================================================

function hashEmail(email: string): number {
  let h = 0;
  for (let i = 0; i < email.length; i++) {
    h = ((h << 5) - h) + email.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

function getInitials(name: string | null, email: string): string {
  if (name) return name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase();
  return email.slice(0, 2).toUpperCase();
}

function MemberAvatar({ name, email }: { name: string | null; email: string }) {
  const color = NONSTATUS_COLORS[hashEmail(email) % NONSTATUS_COLORS.length];
  return (
    <div
      style={{
        width: '26px',
        height: '26px',
        borderRadius: '50%',
        backgroundColor: color,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontSize: '0.7rem',
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {getInitials(name, email)}
    </div>
  );
}

// =============================================================================
// Goal Card
// =============================================================================

interface GoalCardProps {
  goal: Goal;
  canEdit: boolean;
  maxEntries: number;
  onSelect: (goal: Goal) => void;
  onStatusChange: (goal: Goal, status: GoalStatus) => void;
}

function GoalCard({ goal, canEdit, maxEntries, onSelect, onStatusChange }: GoalCardProps) {
  return (
    <Card
      isCompact
      isClickable
      style={{ cursor: 'pointer', marginBottom: '0.75rem' }}
      onClick={() => onSelect(goal)}
    >
      <CardBody>
        <Flex
          justifyContent={{ default: 'justifyContentSpaceBetween' }}
          alignItems={{ default: 'alignItemsFlexStart' }}
        >
          <Flex direction={{ default: 'column' }} spaceItems={{ default: 'spaceItemsXs' }} style={{ flex: 1, minWidth: 0 }}>
            <FlexItem>
              <strong style={{ wordBreak: 'break-word' }}>{goal.title}</strong>
            </FlexItem>
            {goal.description && (
              <FlexItem>
                <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                  {goal.description}
                </Content>
              </FlexItem>
            )}
            <FlexItem>
              <Flex spaceItems={{ default: 'spaceItemsSm' }} style={{ flexWrap: 'wrap', gap: '0.25rem' }}>
                <FlexItem>
                  <Label color={STATUS_COLORS[goal.status]} isCompact>
                    {STATUS_LABELS[goal.status]}
                  </Label>
                </FlexItem>
                <FlexItem>
                  <Label color={HORIZON_COLORS[goal.horizon]} isCompact variant="outline">
                    {HORIZON_LABELS[goal.horizon]}
                  </Label>
                </FlexItem>
                {goal.due_date && (
                  <FlexItem>
                    <Label
                      color={isOverdue(goal.due_date) ? 'red' : isDueSoon(goal.due_date) ? 'orange' : 'grey'}
                      isCompact
                      variant="outline"
                    >
                      Due {formatDueDate(goal.due_date)}
                    </Label>
                  </FlexItem>
                )}
              </Flex>
            </FlexItem>
            <FlexItem>
              <AlignmentBar
                count={goal.entry_link_count}
                max={maxEntries}
                softMax={goal.scope === 'individual' ? 10 : undefined}
              />
            </FlexItem>
          </Flex>
          {canEdit && (
            <FlexItem>
              <Flex spaceItems={{ default: 'spaceItemsXs' }} onClick={(e) => e.stopPropagation()}>
                {goal.status === 'active' && (
                  <FlexItem>
                    <Tooltip content="Mark completed">
                      <Button
                        variant="plain"
                        aria-label="Mark completed"
                        onClick={() => onStatusChange(goal, 'completed')}
                        style={{ color: 'var(--pf-t--global--color--status--success--default)' }}
                      >
                        <CheckCircleIcon />
                      </Button>
                    </Tooltip>
                  </FlexItem>
                )}
                {goal.status !== 'dropped' && (
                  <FlexItem>
                    <Tooltip content="Drop goal">
                      <Button
                        variant="plain"
                        isDanger
                        aria-label="Drop goal"
                        onClick={() => onStatusChange(goal, 'dropped')}
                      >
                        <TimesCircleIcon />
                      </Button>
                    </Tooltip>
                  </FlexItem>
                )}
              </Flex>
            </FlexItem>
          )}
        </Flex>
      </CardBody>
    </Card>
  );
}

// =============================================================================
// Team Goals Summary (ExpandableSection strip)
// =============================================================================

interface TeamGoalsSummaryProps {
  teamGoals: Goal[];
}

function TeamGoalsSummary({ teamGoals }: TeamGoalsSummaryProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (teamGoals.length === 0) return null;

  const activeGoals = teamGoals.filter((g) => g.status === 'active');
  const withEntries = activeGoals.filter((g) => g.entry_link_count > 0);
  const totalLinked = activeGoals.reduce((sum, g) => sum + g.entry_link_count, 0);
  const topGoal = [...activeGoals].sort((a, b) => b.entry_link_count - a.entry_link_count)[0];
  const coveragePct =
    activeGoals.length > 0 ? Math.round((withEntries.length / activeGoals.length) * 100) : 0;

  const toggleContent = (
    <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsMd' }}>
      <FlexItem>
        <BullseyeIcon />
      </FlexItem>
      <FlexItem>
        <strong>Team Goal Health</strong>
      </FlexItem>
      <FlexItem>
        <Label color="green" isCompact>{activeGoals.length} active</Label>
      </FlexItem>
      <FlexItem>
        <Label color={coveragePct >= 60 ? 'green' : coveragePct >= 30 ? 'orange' : 'red'} isCompact>
          {coveragePct}% coverage
        </Label>
      </FlexItem>
      <FlexItem>
        <Label color="grey" isCompact>{totalLinked} total entries</Label>
      </FlexItem>
    </Flex>
  );

  return (
    <GridItem span={12}>
      <Card isCompact style={{ marginBottom: '0.5rem' }}>
        <CardBody style={{ paddingBottom: isExpanded ? 0 : undefined }}>
          <ExpandableSection
            toggleContent={toggleContent}
            isExpanded={isExpanded}
            onToggle={(_e, expanded) => setIsExpanded(expanded)}
            isIndented
          >
            {activeGoals.length > 0 && (
              <Table aria-label="Team goal health" variant="compact">
                <Thead>
                  <Tr>
                    <Th width={40}>Goal</Th>
                    <Th width={15}>Horizon</Th>
                    <Th width={30}>Alignment</Th>
                    <Th width={15}>Status</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {[...activeGoals]
                    .sort((a, b) => b.entry_link_count - a.entry_link_count)
                    .map((g) => (
                      <Tr key={g.id} style={g.id === topGoal?.id ? { fontWeight: 500 } : undefined}>
                        <Td dataLabel="Goal">{g.title}</Td>
                        <Td dataLabel="Horizon">
                          <Label color={HORIZON_COLORS[g.horizon]} isCompact variant="outline">
                            {HORIZON_LABELS[g.horizon]}
                          </Label>
                        </Td>
                        <Td dataLabel="Alignment">
                          <AlignmentBar
                            count={g.entry_link_count}
                            max={activeGoals.reduce((m, x) => Math.max(m, x.entry_link_count), 0)}
                          />
                        </Td>
                        <Td dataLabel="Status">
                          <Label color={STATUS_COLORS[g.status]} isCompact>{STATUS_LABELS[g.status]}</Label>
                        </Td>
                      </Tr>
                    ))}
                </Tbody>
              </Table>
            )}
          </ExpandableSection>
        </CardBody>
      </Card>
    </GridItem>
  );
}

// =============================================================================
// Goal Detail Drawer — edit, notes, linked entries
// =============================================================================

interface GoalDetailDrawerProps {
  goal: Goal | null;
  onClose: () => void;
  canEdit: boolean;
  onStatusChange: (goal: Goal, status: GoalStatus) => void;
  onGoalUpdated?: (updated: Goal) => void;
  onDelete?: (goal: Goal) => void;
}

function GoalDetailDrawer({ goal, onClose, canEdit, onStatusChange, onGoalUpdated, onDelete }: GoalDetailDrawerProps) {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  // ---- Linked entries ----
  const { data: linksData, isLoading: linksLoading } = useQuery({
    queryKey: ['goalLinks', goal?.id],
    queryFn: () => listGoalLinks(goal!.id),
    enabled: !!goal,
  });

  // ---- Notes ----
  const { data: notesData, isLoading: notesLoading } = useQuery({
    queryKey: ['goalNotes', goal?.id],
    queryFn: () => listGoalNotes(goal!.id),
    enabled: !!goal,
  });

  const [noteText, setNoteText] = useState('');
  const addNoteMutation = useMutation({
    mutationFn: (body: string) => createGoalNote(goal!.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goalNotes', goal?.id] });
      setNoteText('');
    },
  });

  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: number) => deleteGoalNote(goal!.id, noteId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goalNotes', goal?.id] }),
  });

  // ---- Inline editing ----
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editHorizon, setEditHorizon] = useState<GoalHorizon>('sprint');
  const [editDueDate, setEditDueDate] = useState('');
  const [editStatus, setEditStatus] = useState<GoalStatus>('active');
  const [editError, setEditError] = useState<string | null>(null);

  // Reset all transient drawer state whenever the selected goal changes
  const goalId = goal?.id ?? null;
  useEffect(() => {
    setEditing(false);
    setEditError(null);
    setNoteText('');
  }, [goalId]);

  const editMutation = useMutation({
    mutationFn: (data: Parameters<typeof updateGoal>[1]) => updateGoal(goal!.id, data),
    onSuccess: (updatedGoal: Goal) => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      setEditing(false);
      setEditError(null);
      onGoalUpdated?.(updatedGoal);
    },
    onError: (err: Error) => setEditError(err.message),
  });

  const startEditing = () => {
    if (!goal) return;
    setEditTitle(goal.title);
    setEditDescription(goal.description ?? '');
    setEditHorizon(goal.horizon);
    setEditDueDate(goal.due_date ? goal.due_date.slice(0, 10) : '');
    setEditStatus(goal.status);
    setEditError(null);
    setEditing(true);
  };

  const handleSaveEdit = () => {
    if (!editTitle.trim()) { setEditError('Title is required'); return; }
    editMutation.mutate({
      title: editTitle.trim(),
      description: editDescription.trim() || undefined,
      horizon: editHorizon,
      due_date: editDueDate || '',
      status: editStatus,
    });
  };

  const links = linksData?.links ?? [];
  const notes = notesData?.notes ?? [];

  const byUser: Record<string, GoalEntryLink[]> = {};
  for (const link of links) {
    const key = link.username ?? 'Unknown';
    byUser[key] = [...(byUser[key] ?? []), link];
  }

  if (!goal) {
    return (
      <DrawerPanelContent widths={{ default: 'width_33' }}>
        <DrawerHead />
      </DrawerPanelContent>
    );
  }

  return (
    <DrawerPanelContent widths={{ default: 'width_33' }} style={{ overflowY: 'auto' }}>
      <DrawerHead>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsFlexStart' }}>
          <FlexItem style={{ flex: 1, minWidth: 0 }}>
            <Title headingLevel="h3" size="md" style={{ wordBreak: 'break-word' }}>{goal.title}</Title>
          </FlexItem>
          <Flex spaceItems={{ default: 'spaceItemsXs' }}>
            {canEdit && !editing && (
              <FlexItem>
                <Tooltip content="Edit goal">
                  <Button variant="plain" aria-label="Edit" onClick={startEditing}>
                    <PencilAltIcon />
                  </Button>
                </Tooltip>
              </FlexItem>
            )}
            {canEdit && !editing && onDelete && (
              <FlexItem>
                <Tooltip content="Delete goal">
                  <Button variant="plain" isDanger aria-label="Delete" onClick={() => onDelete(goal)}>
                    <TrashIcon />
                  </Button>
                </Tooltip>
              </FlexItem>
            )}
            <FlexItem>
              <Button variant="plain" aria-label="Close" onClick={onClose}>✕</Button>
            </FlexItem>
          </Flex>
        </Flex>

        {/* Inline edit form */}
        {editing && goal ? (
          <div style={{ marginTop: '0.75rem' }}>
            {editError && <Alert variant="danger" title={editError} isInline style={{ marginBottom: '0.5rem' }} />}
            <Form>
              <FormGroup label="Title" isRequired fieldId="edit-title">
                <TextInput id="edit-title" value={editTitle} onChange={(_e, v) => setEditTitle(v)} autoFocus />
              </FormGroup>
              <FormGroup label="Description" fieldId="edit-desc">
                <TextArea id="edit-desc" value={editDescription} onChange={(_e, v) => setEditDescription(v)} rows={2} />
              </FormGroup>
              <FormGroup label="Status" fieldId="edit-status">
                <FormSelect id="edit-status" value={editStatus} onChange={(_e, v) => setEditStatus(v as GoalStatus)}>
                  <FormSelectOption value="active" label="Active" />
                  <FormSelectOption value="completed" label="Completed" />
                  <FormSelectOption value="dropped" label="Dropped" />
                </FormSelect>
              </FormGroup>
              <FormGroup label="Time Horizon" fieldId="edit-horizon">
                <FormSelect id="edit-horizon" value={editHorizon} onChange={(_e, v) => {
                  const h = v as GoalHorizon;
                  setEditHorizon(h);
                  if (h === 'ongoing') setEditDueDate('');
                }}>
                  <FormSelectOption value="sprint" label="Sprint" />
                  <FormSelectOption value="quarter" label="Quarter" />
                  <FormSelectOption value="ongoing" label="Ongoing" />
                </FormSelect>
              </FormGroup>
              {editHorizon !== 'ongoing' && (
                <FormGroup label="Due Date" fieldId="edit-due-date">
                  <TextInput id="edit-due-date" type="date" value={editDueDate} onChange={(_e, v) => setEditDueDate(v)} />
                  <Content component="small" style={{ color: t_global_text_color_subtle.var }}>Leave blank to clear</Content>
                </FormGroup>
              )}
            </Form>
            <Flex spaceItems={{ default: 'spaceItemsSm' }} style={{ marginTop: '0.75rem' }}>
              <FlexItem>
                <Button variant="primary" size="sm" onClick={handleSaveEdit} isLoading={editMutation.isPending}>
                  Save
                </Button>
              </FlexItem>
              <FlexItem>
                <Button variant="link" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
              </FlexItem>
            </Flex>
          </div>
        ) : (
          <>
            {goal.description && (
              <Content component="small" style={{ color: t_global_text_color_subtle.var, marginTop: '0.25rem' }}>
                {goal.description}
              </Content>
            )}
            <Flex spaceItems={{ default: 'spaceItemsSm' }} style={{ marginTop: '0.5rem', flexWrap: 'wrap' }}>
              <FlexItem>
                <Label color={STATUS_COLORS[goal.status]} isCompact>{STATUS_LABELS[goal.status]}</Label>
              </FlexItem>
              <FlexItem>
                <Label color={HORIZON_COLORS[goal.horizon]} isCompact variant="outline">
                  {HORIZON_LABELS[goal.horizon]}
                </Label>
              </FlexItem>
              {goal.due_date && (
                <FlexItem>
                  <Label
                    color={isOverdue(goal.due_date) ? 'red' : isDueSoon(goal.due_date) ? 'orange' : 'grey'}
                    isCompact
                    variant="outline"
                  >
                    Due {formatDueDate(goal.due_date)}
                  </Label>
                </FlexItem>
              )}
              <FlexItem>
                <Label color="grey" isCompact>
                  {goal.entry_link_count} {goal.entry_link_count === 1 ? 'entry' : 'entries'}
                </Label>
              </FlexItem>
            </Flex>
            {canEdit && goal.status === 'active' && (
              <Flex spaceItems={{ default: 'spaceItemsSm' }} style={{ marginTop: '0.5rem' }}>
                <FlexItem>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<CheckCircleIcon />}
                    onClick={() => onStatusChange(goal, 'completed')}
                  >
                    Mark Complete
                  </Button>
                </FlexItem>
                <FlexItem>
                  <Button
                    variant="secondary"
                    isDanger
                    size="sm"
                    icon={<TimesCircleIcon />}
                    onClick={() => onStatusChange(goal, 'dropped')}
                  >
                    Drop
                  </Button>
                </FlexItem>
              </Flex>
            )}
          </>
        )}
      </DrawerHead>

      <DrawerPanelBody>
        {/* ---- Notes ---- */}
        <Title headingLevel="h4" size="md" style={{ marginBottom: '0.75rem' }}>Notes</Title>
        {notesLoading ? (
          <Spinner size="md" />
        ) : notes.length === 0 ? (
          <Content component="small" style={{ color: t_global_text_color_subtle.var, display: 'block', marginBottom: '0.75rem' }}>
            No notes yet. Add the first one below.
          </Content>
        ) : (
          <div style={{ marginBottom: '0.75rem' }}>
            {notes.map((note: GoalNote) => (
              <div
                key={note.id}
                style={{
                  marginBottom: '0.75rem',
                  padding: '0.5rem 0.75rem',
                  border: '1px solid var(--pf-t--global--border--color--default)',
                  borderLeft: '3px solid var(--pf-t--global--border--color--default)',
                  borderRadius: '4px',
                }}
              >
                <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsFlexStart' }}>
                  <FlexItem>
                    <Flex spaceItems={{ default: 'spaceItemsSm' }} alignItems={{ default: 'alignItemsCenter' }}>
                      <FlexItem>
                        <MemberAvatar
                          name={note.author_display_name}
                          email={note.author_email ?? 'unknown'}
                        />
                      </FlexItem>
                      <FlexItem>
                        <Content component="small" style={{ fontWeight: 600 }}>
                          {note.author_display_name ?? note.author_email ?? 'Unknown'}
                        </Content>
                        <Content component="small" style={{ color: t_global_text_color_subtle.var, display: 'block' }}>
                          {note.created_at ? new Date(note.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                        </Content>
                      </FlexItem>
                    </Flex>
                  </FlexItem>
                  {(note.author_id === user?.id || user?.role === 'admin' || user?.role === 'manager') && (
                    <FlexItem>
                      <Button
                        variant="plain"
                        aria-label="Delete note"
                        onClick={() => deleteNoteMutation.mutate(note.id)}
                        style={{ color: t_global_text_color_subtle.var }}
                      >
                        <TrashIcon />
                      </Button>
                    </FlexItem>
                  )}
                </Flex>
                <div style={{ marginTop: '0.4rem', whiteSpace: 'pre-wrap', fontSize: '0.875rem' }}>
                  {note.body}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Add note form */}
        <Flex direction={{ default: 'column' }} spaceItems={{ default: 'spaceItemsSm' }}>
          <FlexItem>
            <TextArea
              value={noteText}
              onChange={(_e, v) => setNoteText(v)}
              placeholder="Add a note..."
              rows={2}
              aria-label="New note"
            />
          </FlexItem>
          <FlexItem>
            <Button
              variant="secondary"
              size="sm"
              isDisabled={!noteText.trim()}
              isLoading={addNoteMutation.isPending}
              onClick={() => addNoteMutation.mutate(noteText)}
            >
              Add Note
            </Button>
          </FlexItem>
        </Flex>

        <Divider style={{ margin: '1rem 0' }} />

        {/* ---- Linked entries ---- */}
        <Title headingLevel="h4" size="md" style={{ marginBottom: '0.75rem' }}>Linked Report Entries</Title>
        {linksLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="md" />
          </Flex>
        ) : links.length === 0 ? (
          <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
            No report entries linked yet. Open a report and use "Link to Goal" on an entry.
          </Content>
        ) : (
          Object.entries(byUser).map(([username, userLinks]) => (
            <div key={username} style={{ marginBottom: '1.25rem' }}>
              <Content component="small" style={{ fontWeight: 600, marginBottom: '0.5rem', display: 'block' }}>
                {username}
              </Content>
              {userLinks.map((link) => (
                <div
                  key={link.id}
                  style={{
                    padding: '0.5rem 0.75rem',
                    marginBottom: '0.5rem',
                    border: '1px solid var(--pf-t--global--border--color--default)',
                    borderLeft: '3px solid var(--pf-t--global--border--color--default)',
                    borderRadius: '0 4px 4px 0',
                  }}
                >
                  {link.entry_text ? (
                    <InlineMarkdown>{link.entry_text}</InlineMarkdown>
                  ) : (
                    <Content component="small" style={{ color: t_global_text_color_subtle.var, fontStyle: 'italic' }}>
                      Entry text unavailable
                    </Content>
                  )}
                  {link.entry_ticket_key && (
                    <div style={{ marginTop: '0.25rem' }}>
                      <Label color="blue" isCompact>{link.entry_ticket_key}</Label>
                    </div>
                  )}
                  {link.report_period && (
                    <Content component="small" style={{ color: t_global_text_color_subtle.var, display: 'block', marginTop: '0.25rem' }}>
                      {link.report_period}
                    </Content>
                  )}
                </div>
              ))}
            </div>
          ))
        )}
      </DrawerPanelBody>
    </DrawerPanelContent>
  );
}

// =============================================================================
// Create Goal Modal
//
// Rules:
//  - When scope is forced (button origin is "Add Goal" or "Add Team Goal"),
//    the scope field is hidden — no redundant selector.
//  - Individual goals: team is auto-assigned to the user's first team.
//    No team picker shown — the user doesn't manage teams.
//  - Team goals: team picker shown only when the user belongs to / manages
//    more than one team (admins); otherwise auto-assigned.
//  - The single "New Goal" header button (admin shortcut) shows a scope
//    toggle, and the team picker appears only when scope = 'team'.
// =============================================================================

interface CreateGoalModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Pre-set scope. When provided the scope field is hidden. */
  defaultScope: GoalScope;
  defaultTeamId: number | null;
  /** Whether the caller allows the user to switch to team scope. */
  canChooseScope: boolean;
}

function CreateGoalModal({ isOpen, onClose, defaultScope, defaultTeamId, canChooseScope }: CreateGoalModalProps) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [scope, setScope] = useState<GoalScope>(defaultScope);
  const [horizon, setHorizon] = useState<GoalHorizon>('sprint');
  const [dueDate, setDueDate] = useState<string>(defaultDueDateForHorizon('sprint') ?? '');
  const [teamId, setTeamId] = useState<number | null>(defaultTeamId);
  const [error, setError] = useState<string | null>(null);

  // Reset all form state whenever the modal is opened so it always reflects
  // the current defaultScope/defaultTeamId (the modal stays mounted between opens).
  useEffect(() => {
    if (isOpen) {
      setTitle('');
      setDescription('');
      setScope(defaultScope);
      setHorizon('sprint');
      setDueDate(defaultDueDateForHorizon('sprint') ?? '');
      setTeamId(defaultTeamId);
      setError(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => listTeams({ all_teams: true }),
    enabled: isOpen,
  });

  // When teams load, pick the first one as default if not yet set
  const teams = teamsData?.teams ?? [];
  const resolvedTeamId = teamId ?? teams[0]?.id ?? null;

  const createMutation = useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      handleClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  const handleHorizonChange = (h: GoalHorizon) => {
    setHorizon(h);
    // Auto-update the due date suggestion when horizon changes, but only if the
    // user hasn't manually changed it away from the previous auto-value
    const auto = defaultDueDateForHorizon(h);
    setDueDate(auto ?? '');
  };

  const handleClose = () => {
    setTitle('');
    setDescription('');
    setScope(defaultScope);
    setHorizon('sprint');
    setDueDate(defaultDueDateForHorizon('sprint') ?? '');
    setTeamId(defaultTeamId);
    setError(null);
    onClose();
  };

  const handleSubmit = () => {
    if (!title.trim()) { setError('Title is required'); return; }
    if (!resolvedTeamId) { setError('No team found — contact your admin.'); return; }
    createMutation.mutate({
      title: title.trim(),
      description: description.trim() || undefined,
      scope,
      team_id: resolvedTeamId,
      horizon,
      due_date: dueDate || undefined,
    });
  };

  // Team picker always visible for team goals — even with one team, shows the user where it lands
  const showTeamPicker = scope === 'team';
  // Title changes based on scope
  const modalTitle = scope === 'team' ? 'Create Team Goal' : 'Create Personal Goal';

  return (
    <Modal isOpen={isOpen} onClose={handleClose} variant="small">
      <ModalHeader title={modalTitle} />
      <ModalBody>
        {error && <Alert variant="danger" title={error} isInline style={{ marginBottom: '1rem' }} />}
        <Form>
          {/* Scope toggle — only shown when the origin button doesn't lock the scope */}
          {canChooseScope && (
            <FormGroup label="Goal Type" isRequired fieldId="goal-scope">
              <FormSelect
                id="goal-scope"
                value={scope}
                onChange={(_e, v) => setScope(v as GoalScope)}
              >
                <FormSelectOption value="individual" label="Personal — applies only to me" />
                <FormSelectOption value="team" label="Team — visible and shared across the team" />
              </FormSelect>
            </FormGroup>
          )}

          <FormGroup label="Title" isRequired fieldId="goal-title">
            <TextInput
              id="goal-title"
              value={title}
              onChange={(_e, v) => setTitle(v)}
              placeholder={
                scope === 'team'
                  ? 'e.g. Ship auth refactor by end of quarter'
                  : 'e.g. Complete onboarding to auth service'
              }
              autoFocus
            />
          </FormGroup>

          <FormGroup label="Description" fieldId="goal-description">
            <TextArea
              id="goal-description"
              value={description}
              onChange={(_e, v) => setDescription(v)}
              placeholder="Optional context or acceptance criteria"
              rows={2}
            />
          </FormGroup>

          <FormGroup label="Time Horizon" isRequired fieldId="goal-horizon">
            <FormSelect
              id="goal-horizon"
              value={horizon}
              onChange={(_e, v) => handleHorizonChange(v as GoalHorizon)}
            >
              <FormSelectOption value="sprint" label="Sprint (~2 weeks)" />
              <FormSelectOption value="quarter" label="Quarter (end of current calendar quarter)" />
              <FormSelectOption value="ongoing" label="Ongoing (no due date)" />
            </FormSelect>
          </FormGroup>

          {horizon !== 'ongoing' && (
            <FormGroup label="Due Date" fieldId="goal-due-date">
              <TextInput
                id="goal-due-date"
                type="date"
                value={dueDate}
                onChange={(_e, v) => setDueDate(v)}
              />
              <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                Auto-calculated from horizon — feel free to adjust
              </Content>
            </FormGroup>
          )}

          {/* Team picker only for team goals with multiple teams */}
          {showTeamPicker && (
            <FormGroup label="Team" isRequired fieldId="goal-team">
              <FormSelect
                id="goal-team"
                value={resolvedTeamId ?? ''}
                onChange={(_e, v) => setTeamId(Number(v))}
              >
                {teams.map((t) => (
                  <FormSelectOption key={t.id} value={t.id} label={t.name} />
                ))}
              </FormSelect>
            </FormGroup>
          )}
        </Form>
      </ModalBody>
      <ModalFooter>
        <Button
          variant="primary"
          onClick={handleSubmit}
          isLoading={createMutation.isPending}
          isDisabled={!title.trim()}
        >
          {scope === 'team' ? 'Create Team Goal' : 'Create Personal Goal'}
        </Button>
        <Button variant="link" onClick={handleClose}>Cancel</Button>
      </ModalFooter>
    </Modal>
  );
}

// =============================================================================
// Ticket Activity Section (expandable rows, consistent with ManagementReports)
// =============================================================================

interface TicketActivityProps {
  periodDays: number;
}

function TicketActivity({ periodDays }: TicketActivityProps) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ['ticketActivity', periodDays],
    queryFn: () => getTicketActivity({ period_days: periodDays }),
  });

  const members: MemberTicketActivity[] = data?.members ?? [];

  const toggleRow = (userId: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  return (
    <GridItem span={12}>
      <Card>
        <CardBody>
          <Flex
            justifyContent={{ default: 'justifyContentSpaceBetween' }}
            alignItems={{ default: 'alignItemsCenter' }}
            style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}
          >
            <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsMd' }}>
              <FlexItem><TagIcon /></FlexItem>
              <FlexItem><strong>Ticket Activity</strong></FlexItem>
              {data && (
                <FlexItem>
                  <Label color="blue" isCompact>
                    {data.team_unique_tickets} unique {data.team_unique_tickets === 1 ? 'ticket' : 'tickets'} — team total
                  </Label>
                </FlexItem>
              )}
            </Flex>
            <FlexItem>
              <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                Last {periodDays} days · from report entries
              </Content>
            </FlexItem>
          </Flex>

          {isLoading ? (
            <Flex justifyContent={{ default: 'justifyContentCenter' }}>
              <Spinner size="xl" />
            </Flex>
          ) : members.length === 0 ? (
            <EmptyState titleText="No ticket activity" headingLevel="h4" icon={TagIcon}>
              <EmptyStateBody>
                No ticket keys found in report entries for the selected period.
                Entries need a <code>ticket_key</code> set when submitting reports.
              </EmptyStateBody>
            </EmptyState>
          ) : (
            <Table aria-label="Ticket activity per member" variant="compact">
              <Thead>
                <Tr>
                  <Th screenReaderText="Row expansion" />
                  <Th width={35}>Member</Th>
                  <Th width={15}>Unique Tickets</Th>
                  <Th>Top Tickets</Th>
                  <Th width={15}>Summary</Th>
                </Tr>
              </Thead>
              {members.map((m, rowIndex) => {
                const isExpanded = expandedRows.has(m.user_id);
                const preview = m.tickets.slice(0, 3);
                const overflow = m.tickets.length - preview.length;

                return (
                  <Tbody key={m.user_id} isExpanded={isExpanded}>
                    <Tr>
                      <Td
                        expand={{
                          rowIndex,
                          isExpanded,
                          onToggle: () => toggleRow(m.user_id),
                          expandId: `ticket-expand-${m.user_id}`,
                        }}
                      />
                      <Td dataLabel="Member">
                        <Flex
                          spaceItems={{ default: 'spaceItemsSm' }}
                          alignItems={{ default: 'alignItemsCenter' }}
                          flexWrap={{ default: 'nowrap' }}
                        >
                          <FlexItem>
                            <MemberAvatar name={m.display_name} email={m.email} />
                          </FlexItem>
                          <FlexItem>
                            <div style={{ fontWeight: 500 }}>
                              {m.display_name || m.email.split('@')[0]}
                            </div>
                            <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                              {m.email}
                            </Content>
                          </FlexItem>
                        </Flex>
                      </Td>
                      <Td dataLabel="Unique Tickets" modifier="nowrap">
                        <strong>{m.unique_tickets}</strong>
                      </Td>
                      <Td dataLabel="Top Tickets">
                        {m.unique_tickets === 0 ? (
                          <span style={{ color: t_global_text_color_subtle.var }}>—</span>
                        ) : (
                          <Flex spaceItems={{ default: 'spaceItemsXs' }} flexWrap={{ default: 'wrap' }}>
                            {preview.map((t) => (
                              <FlexItem key={t}>
                                <Label color="blue" isCompact>{t}</Label>
                              </FlexItem>
                            ))}
                            {overflow > 0 && (
                              <FlexItem>
                                <Button
                                  variant="link"
                                  isInline
                                  onClick={() => toggleRow(m.user_id)}
                                  style={{ fontSize: '0.8rem' }}
                                >
                                  +{overflow} more
                                </Button>
                              </FlexItem>
                            )}
                          </Flex>
                        )}
                      </Td>
                      <Td dataLabel="Summary" modifier="nowrap">
                        <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                          {m.tickets.length > 0
                            ? `${m.unique_tickets} in last ${periodDays}d`
                            : '—'}
                        </Content>
                      </Td>
                    </Tr>
                    <Tr isExpanded={isExpanded}>
                      <Td colSpan={5} noPadding>
                        <ExpandableRowContent>
                          <div style={{ padding: '0.75rem 1.5rem' }}>
                            <Content component="small" style={{ fontWeight: 600, display: 'block', marginBottom: '0.5rem' }}>
                              All tickets referenced by {m.display_name || m.email.split('@')[0]} (last {periodDays} days)
                            </Content>
                            {m.tickets.length === 0 ? (
                              <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                                No tickets referenced.
                              </Content>
                            ) : (
                              <Flex spaceItems={{ default: 'spaceItemsSm' }} flexWrap={{ default: 'wrap' }}>
                                {m.tickets.map((t) => (
                                  <FlexItem key={t}>
                                    <Label color="blue">{t}</Label>
                                  </FlexItem>
                                ))}
                              </Flex>
                            )}
                          </div>
                        </ExpandableRowContent>
                      </Td>
                    </Tr>
                  </Tbody>
                );
              })}
            </Table>
          )}
        </CardBody>
      </Card>
    </GridItem>
  );
}

// =============================================================================
// Team Members' Individual Goals Table (manager view)
// =============================================================================

interface TeamMemberGoalsTableProps {
  goals: Goal[];
  onSelect: (goal: Goal) => void;
  onStatusChange: (goal: Goal, status: GoalStatus) => void;
}

function TeamMemberGoalsTable({ goals, onSelect, onStatusChange }: TeamMemberGoalsTableProps) {
  const [expandedOwners, setExpandedOwners] = useState<Set<number>>(new Set());

  if (goals.length === 0) return null;

  const byOwner = new Map<number, { name: string | null; email: string; goals: Goal[] }>();
  for (const g of goals) {
    const ownerId = g.owner_id ?? -1;
    if (!byOwner.has(ownerId)) {
      byOwner.set(ownerId, {
        name: g.owner_display_name ?? null,
        email: g.owner_email ?? `user-${ownerId}`,
        goals: [],
      });
    }
    byOwner.get(ownerId)!.goals.push(g);
  }

  const toggleOwner = (ownerId: number) => {
    setExpandedOwners((prev) => {
      const next = new Set(prev);
      if (next.has(ownerId)) next.delete(ownerId);
      else next.add(ownerId);
      return next;
    });
  };

  const ownerEntries = Array.from(byOwner.entries());

  return (
    <GridItem span={12}>
      <Card>
        <CardBody>
          <Title headingLevel="h2" size="lg" style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}>
            Team Members' Individual Goals
          </Title>
          <Table aria-label="Team members individual goals" variant="compact">
            <Thead>
              <Tr>
                <Th screenReaderText="Row expansion" />
                <Th width={40}>Member</Th>
                <Th width={15}>Active Goals</Th>
                <Th width={30}>Top Goal</Th>
                <Th width={15}>Total Entries</Th>
              </Tr>
            </Thead>
            {ownerEntries.map(([ownerId, ownerData], rowIndex) => {
              const isExpanded = expandedOwners.has(ownerId);
              const activeGoals = ownerData.goals.filter((g) => g.status === 'active');
              const topGoal = [...ownerData.goals].sort((a, b) => b.entry_link_count - a.entry_link_count)[0];
              const totalEntries = ownerData.goals.reduce((s, g) => s + g.entry_link_count, 0);

              const displayName = ownerData.name || ownerData.email.split('@')[0];

              return (
                <Tbody key={ownerId} isExpanded={isExpanded}>
                  <Tr>
                    <Td
                      expand={{
                        rowIndex,
                        isExpanded,
                        onToggle: () => toggleOwner(ownerId),
                        expandId: `owner-expand-${ownerId}`,
                      }}
                    />
                    <Td dataLabel="Member">
                      <Flex spaceItems={{ default: 'spaceItemsSm' }} alignItems={{ default: 'alignItemsCenter' }}>
                        <FlexItem>
                          <MemberAvatar name={ownerData.name} email={ownerData.email} />
                        </FlexItem>
                        <FlexItem>
                          <div style={{ fontWeight: 500 }}>{displayName}</div>
                          <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                            {ownerData.email}
                          </Content>
                        </FlexItem>
                      </Flex>
                    </Td>
                    <Td dataLabel="Active Goals" modifier="nowrap">
                      {activeGoals.length > 0 ? (
                        <Label color="blue" isCompact>{activeGoals.length}</Label>
                      ) : (
                        <span style={{ color: t_global_text_color_subtle.var }}>—</span>
                      )}
                    </Td>
                    <Td dataLabel="Top Goal">
                      {topGoal ? (
                        <Button
                          variant="link"
                          isInline
                          onClick={() => onSelect(topGoal)}
                          style={{ textAlign: 'left', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}
                        >
                          {topGoal.title}
                        </Button>
                      ) : (
                        <span style={{ color: t_global_text_color_subtle.var }}>—</span>
                      )}
                    </Td>
                    <Td dataLabel="Total Entries" modifier="nowrap">
                      {totalEntries > 0 ? <strong>{totalEntries}</strong> : <span style={{ color: t_global_text_color_subtle.var }}>—</span>}
                    </Td>
                  </Tr>
                  <Tr isExpanded={isExpanded}>
                    <Td colSpan={5} noPadding>
                      <ExpandableRowContent>
                        <div style={{ padding: '0.75rem 1.5rem' }}>
                          <Flex direction={{ default: 'column' }} spaceItems={{ default: 'spaceItemsSm' }}>
                            {ownerData.goals.map((g) => (
                              <FlexItem key={g.id}>
                                <Flex
                                  spaceItems={{ default: 'spaceItemsMd' }}
                                  alignItems={{ default: 'alignItemsCenter' }}
                                  style={{
                                    padding: '0.5rem 0.75rem',
                                    border: '1px solid var(--pf-t--global--border--color--default)',
                                    borderLeft: '3px solid var(--pf-t--global--border--color--default)',
                                    borderRadius: '0 4px 4px 0',
                                    cursor: 'pointer',
                                  }}
                                  onClick={() => onSelect(g)}
                                >
                                  <FlexItem style={{ flex: 1 }}>
                                    <div><strong>{g.title}</strong></div>
                                    {g.description && (
                                      <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                                        {g.description}
                                      </Content>
                                    )}
                                  </FlexItem>
                                  <FlexItem>
                                    <Label color={STATUS_COLORS[g.status]} isCompact>{STATUS_LABELS[g.status]}</Label>
                                  </FlexItem>
                                  <FlexItem>
                                    <Label color={HORIZON_COLORS[g.horizon]} isCompact variant="outline">
                                      {HORIZON_LABELS[g.horizon]}
                                    </Label>
                                  </FlexItem>
                                  <FlexItem>
                                    <AlignmentBar count={g.entry_link_count} max={10} />
                                  </FlexItem>
                                  {g.status !== 'dropped' && (
                                    <FlexItem onClick={(e) => e.stopPropagation()}>
                                      <Tooltip content={g.status === 'active' ? 'Mark completed' : 'Drop'}>
                                        <Button
                                          variant="plain"
                                          size="sm"
                                          aria-label={g.status === 'active' ? 'Mark completed' : 'Drop goal'}
                                          onClick={() => onStatusChange(g, g.status === 'active' ? 'completed' : 'dropped')}
                                          style={g.status === 'active' ? { color: 'var(--pf-t--global--color--status--success--default)' } : undefined}
                                          isDanger={g.status !== 'active'}
                                        >
                                          {g.status === 'active' ? <CheckCircleIcon /> : <TimesCircleIcon />}
                                        </Button>
                                      </Tooltip>
                                    </FlexItem>
                                  )}
                                </Flex>
                              </FlexItem>
                            ))}
                          </Flex>
                        </div>
                      </ExpandableRowContent>
                    </Td>
                  </Tr>
                </Tbody>
              );
            })}
          </Table>
        </CardBody>
      </Card>
    </GridItem>
  );
}

// =============================================================================
// Main Page
// =============================================================================

export function GoalsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isManager = user?.role === 'manager' || user?.role === 'admin';

  const [selectedGoal, setSelectedGoal] = useState<Goal | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createScope, setCreateScope] = useState<GoalScope>('individual');
  // true = scope selector is shown (generic "New Goal" button); false = scope is locked by the button origin
  const [canChooseScope, setCanChooseScope] = useState(false);
  const [statusFilter, setStatusFilter] = useState<GoalStatus | 'all'>('active');
  const [periodDays, setPeriodDays] = useState(30);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [updateSuccess, setUpdateSuccess] = useState<string | null>(null);

  const { data: goalsData, isLoading } = useQuery({
    queryKey: ['goals'],
    queryFn: listGoals,
  });

  const { data: teamsData } = useQuery({
    queryKey: ['teams'],
    queryFn: () => listTeams({ all_teams: true }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateGoal>[1] }) =>
      updateGoal(id, data),
    onSuccess: (_updated, variables) => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      if (variables.data.status) {
        const label = { active: 'Active', completed: 'Completed', dropped: 'Dropped' }[variables.data.status] ?? variables.data.status;
        setUpdateSuccess(`Goal marked as ${label}.`);
        setTimeout(() => setUpdateSuccess(null), 3000);
      }
      setUpdateError(null);
    },
    onError: (err: Error) => {
      setUpdateError(`Failed to update goal: ${err.message}`);
      setTimeout(() => setUpdateError(null), 5000);
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      setSelectedGoal(null);
    },
  });

  const defaultTeamId = teamsData?.teams[0]?.id ?? null;

  const allGoals = goalsData?.goals ?? [];
  const filtered = statusFilter === 'all' ? allGoals : allGoals.filter((g) => g.status === statusFilter);

  const teamGoals = filtered.filter((g) => g.scope === 'team');
  const myGoals = filtered.filter((g) => g.scope === 'individual' && g.owner_id === user?.id);
  const otherIndividualGoals = isManager
    ? filtered.filter((g) => g.scope === 'individual' && g.owner_id !== user?.id)
    : [];

  const maxTeamEntries = teamGoals.reduce((m, g) => Math.max(m, g.entry_link_count), 0);
  const maxMyEntries = myGoals.reduce((m, g) => Math.max(m, g.entry_link_count), 0);

  /**
   * Open the create modal.
   * - scope: pre-set scope
   * - chooseScope: whether to show the scope toggle (true = generic "New Goal", false = button-locked)
   */
  const handleOpenCreate = (scope: GoalScope, chooseScope = false) => {
    setCreateScope(scope);
    setCanChooseScope(chooseScope);
    setCreateModalOpen(true);
  };

  const deleteMutation = useMutation({
    mutationFn: (goalId: number) => deleteGoal(goalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goals'] });
      setSelectedGoal(null);
      setUpdateSuccess('Goal deleted.');
      setTimeout(() => setUpdateSuccess(null), 3000);
    },
    onError: (err: Error) => {
      setUpdateError(`Failed to delete goal: ${err.message}`);
      setTimeout(() => setUpdateError(null), 5000);
    },
  });

  const handleDelete = (goal: Goal) => {
    if (!window.confirm(`Permanently delete "${goal.title}"? This will also remove all linked entries and notes.`)) return;
    deleteMutation.mutate(goal.id);
  };

  const handleStatusChange = (goal: Goal, newStatus: GoalStatus) => {
    const label = STATUS_LABELS[newStatus];
    if (newStatus === 'completed' || newStatus === 'dropped') {
      if (!window.confirm(`Mark "${goal.title}" as ${label}?`)) return;
    }
    updateMutation.mutate({ id: goal.id, data: { status: newStatus } });
  };

  return (
    <>
      {updateError && (
        <Alert
          variant="danger"
          title={updateError}
          isInline
          style={{ position: 'sticky', top: 0, zIndex: 200 }}
          actionClose={<Button variant="plain" onClick={() => setUpdateError(null)}>✕</Button>}
        />
      )}
      {updateSuccess && (
        <Alert
          variant="success"
          title={updateSuccess}
          isInline
          style={{ position: 'sticky', top: 0, zIndex: 200 }}
        />
      )}
      <PageSection>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
          <FlexItem>
            <Content>
              <Title headingLevel="h1">Goals</Title>
              <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                Link your report entries to goals — team-wide and personal.
              </Content>
            </Content>
          </FlexItem>
          <FlexItem>
            <Flex spaceItems={{ default: 'spaceItemsSm' }}>
              {isManager && (
                <FlexItem>
                  <FormSelect
                    value={periodDays}
                    onChange={(_e, v) => setPeriodDays(Number(v))}
                    aria-label="Activity period"
                    style={{ minWidth: '130px' }}
                  >
                    <FormSelectOption value={7} label="Last 7 days" />
                    <FormSelectOption value={14} label="Last 14 days" />
                    <FormSelectOption value={30} label="Last 30 days" />
                    <FormSelectOption value={90} label="Last 90 days" />
                  </FormSelect>
                </FlexItem>
              )}
              <FlexItem>
                <FormSelect
                  value={statusFilter}
                  onChange={(_e, v) => setStatusFilter(v as GoalStatus | 'all')}
                  aria-label="Filter by status"
                  style={{ minWidth: '140px' }}
                >
                  <FormSelectOption value="all" label="All Statuses" />
                  <FormSelectOption value="active" label="Active" />
                  <FormSelectOption value="completed" label="Completed" />
                  <FormSelectOption value="dropped" label="Dropped" />
                </FormSelect>
              </FlexItem>
              <FlexItem>
                <Button
                  variant="primary"
                  icon={<PlusIcon />}
                  onClick={() => handleOpenCreate('individual', isManager)}
                >
                  New Goal
                </Button>
              </FlexItem>
            </Flex>
          </FlexItem>
        </Flex>
      </PageSection>

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : (
          <Drawer isExpanded={!!selectedGoal} position="right">
            <DrawerContent panelContent={
              <GoalDetailDrawer
                goal={selectedGoal}
                onClose={() => setSelectedGoal(null)}
                canEdit={
                  !!selectedGoal && (
                    isManager ||
                    (selectedGoal.scope === 'individual' && selectedGoal.owner_id === user?.id)
                  )
                }
                onStatusChange={(goal, status) => {
                  handleStatusChange(goal, status);
                  if (status !== 'active' && statusFilter === 'active') {
                    setSelectedGoal(null);
                  } else {
                    setSelectedGoal({ ...goal, status });
                  }
                }}
                onGoalUpdated={(updated) => setSelectedGoal(updated)}
                onDelete={handleDelete}
              />
            }>
              <DrawerContentBody>
                <Grid hasGutter>
                  {/* Manager team health summary strip */}
                  {isManager && statusFilter !== 'dropped' && (
                    <TeamGoalsSummary teamGoals={allGoals.filter((g) => g.scope === 'team')} />
                  )}

                  {/* Team Goals */}
                  <GridItem span={12} lg={isManager ? 6 : 12}>
                    <Card>
                      <CardBody>
                        <Flex
                          justifyContent={{ default: 'justifyContentSpaceBetween' }}
                          alignItems={{ default: 'alignItemsCenter' }}
                          style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}
                        >
                          <FlexItem>
                            <Title headingLevel="h2" size="lg">Team Goals</Title>
                          </FlexItem>
                          {isManager && (
                            <FlexItem>
                              <Button
                                variant="link"
                                isInline
                                icon={<PlusIcon />}
                                onClick={() => handleOpenCreate('team')}
                              >
                                Add Team Goal
                              </Button>
                            </FlexItem>
                          )}
                        </Flex>
                        {teamGoals.length === 0 ? (
                          <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                            {statusFilter === 'active'
                              ? 'No active team goals. Managers can create team goals here.'
                              : 'No team goals match the selected filter.'}
                          </Content>
                        ) : (
                          teamGoals.map((g) => (
                            <GoalCard
                              key={g.id}
                              goal={g}
                              canEdit={isManager}
                              maxEntries={maxTeamEntries}
                              onSelect={setSelectedGoal}
                              onStatusChange={handleStatusChange}
                            />
                          ))
                        )}
                      </CardBody>
                    </Card>
                  </GridItem>

                  {/* My Goals */}
                  <GridItem span={12} lg={isManager ? 6 : 12}>
                    <Card>
                      <CardBody>
                        <Flex
                          justifyContent={{ default: 'justifyContentSpaceBetween' }}
                          alignItems={{ default: 'alignItemsCenter' }}
                          style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}
                        >
                          <FlexItem>
                            <Title headingLevel="h2" size="lg">My Goals</Title>
                          </FlexItem>
                          <FlexItem>
                            <Button
                              variant="link"
                              isInline
                              icon={<PlusIcon />}
                              onClick={() => handleOpenCreate('individual')}
                            >
                              Add Goal
                            </Button>
                          </FlexItem>
                        </Flex>
                        {myGoals.length === 0 ? (
                          <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                            {statusFilter === 'active'
                              ? 'No active personal goals. Click "Add Goal" to create one.'
                              : 'No personal goals match the selected filter.'}
                          </Content>
                        ) : (
                          myGoals.map((g) => (
                            <GoalCard
                              key={g.id}
                              goal={g}
                              canEdit
                              maxEntries={maxMyEntries}
                              onSelect={setSelectedGoal}
                              onStatusChange={handleStatusChange}
                            />
                          ))
                        )}
                      </CardBody>
                    </Card>
                  </GridItem>

                  {/* Team Members' Individual Goals (manager) — expandable table */}
                  {isManager && otherIndividualGoals.length > 0 && (
                    <TeamMemberGoalsTable
                      goals={otherIndividualGoals}
                      onSelect={setSelectedGoal}
                      onStatusChange={handleStatusChange}
                    />
                  )}

                  {/* Ticket Activity (manager/admin only) — expandable table */}
                  {isManager && <TicketActivity periodDays={periodDays} />}
                </Grid>
              </DrawerContentBody>
            </DrawerContent>
          </Drawer>
        )}
      </PageSection>

      <CreateGoalModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        defaultScope={createScope}
        defaultTeamId={defaultTeamId}
        canChooseScope={canChooseScope}
      />
    </>
  );
}

export default GoalsPage;

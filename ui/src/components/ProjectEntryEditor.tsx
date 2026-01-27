/**
 * Project Entry Editor - Editor for entries within a project in the consolidated view.
 * Shows a flat list of entries (not grouped by user) with optional user attribution.
 * Provides click-to-edit UX and 3-dots menu for user assignment.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Button,
  Card,
  CardBody,
  CardTitle,
  Dropdown,
  DropdownItem,
  DropdownList,
  Flex,
  FlexItem,
  Label,
  MenuToggle,
  MenuToggleElement,
  TextInput,
  Tooltip,
} from '@patternfly/react-core';
import {
  CheckIcon,
  EllipsisVIcon,
  PencilAltIcon,
  PlusIcon,
  TimesIcon,
  TrashIcon,
  UserIcon,
} from '@patternfly/react-icons';
import { InlineMarkdown } from '@/components/StyledMarkdown';

export interface ProjectEntry {
  text: string;
  originalReportId?: number;
  originalUsername?: string;
  isManagerAdded: boolean;
}

export interface TeamMember {
  email: string;
  displayName: string;
}

export interface ProjectEntryEditorProps {
  /** Project ID */
  projectId: number;
  /** Project name for display */
  projectName: string;
  /** Project description (optional) */
  projectDescription?: string | null;
  /** The entries to display/edit */
  entries: ProjectEntry[];
  /** Team members for user assignment dropdown */
  teamMembers: TeamMember[];
  /** Whether editing is enabled */
  isEditing: boolean;
  /** Callback when entries change */
  onEntriesChange: (entries: ProjectEntry[]) => void;
  /** Placeholder text for new entries */
  placeholder?: string;
}

/**
 * Get display name from email address
 */
function getDisplayName(email: string): string {
  return email.split('@')[0];
}

export function ProjectEntryEditor({
  projectName,
  projectDescription,
  entries,
  teamMembers,
  isEditing,
  onEntriesChange,
  placeholder = 'Work item description...',
}: ProjectEntryEditorProps) {
  // Track which entry index is being edited (-1 = none)
  const [editingIndex, setEditingIndex] = useState<number>(-1);
  // Temporary text while editing (before save)
  const [editText, setEditText] = useState<string>('');
  // Track which entry has open dropdown menu
  const [openMenuIndex, setOpenMenuIndex] = useState<number>(-1);
  // Track which entry has open user assignment submenu
  const [openUserMenuIndex, setOpenUserMenuIndex] = useState<number>(-1);
  // Ref to focus input when editing starts
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset editing state when editing mode is turned off
  useEffect(() => {
    if (!isEditing) {
      setEditingIndex(-1);
      setEditText('');
      setOpenMenuIndex(-1);
      setOpenUserMenuIndex(-1);
    }
  }, [isEditing]);

  // Focus input when editing starts
  useEffect(() => {
    if (editingIndex >= 0 && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editingIndex]);

  // Start editing an entry
  const handleStartEdit = useCallback((index: number) => {
    if (!isEditing) return;
    setEditingIndex(index);
    setEditText(entries[index].text);
    setOpenMenuIndex(-1);
  }, [entries, isEditing]);

  // Save the current edit
  const handleSaveEdit = useCallback(() => {
    if (editingIndex >= 0) {
      const newEntries = [...entries];
      newEntries[editingIndex] = { ...newEntries[editingIndex], text: editText };
      onEntriesChange(newEntries);
      setEditingIndex(-1);
      setEditText('');
    }
  }, [editingIndex, editText, entries, onEntriesChange]);

  // Cancel the current edit
  const handleCancelEdit = useCallback(() => {
    setEditingIndex(-1);
    setEditText('');
  }, []);

  // Handle keyboard events in edit mode
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  }, [handleSaveEdit, handleCancelEdit]);

  // Add a new entry (manager-added, no user attribution)
  const handleAddEntry = useCallback(() => {
    const newEntries: ProjectEntry[] = [
      ...entries,
      { text: '', isManagerAdded: true }
    ];
    onEntriesChange(newEntries);
    // Start editing the new entry
    setEditingIndex(newEntries.length - 1);
    setEditText('');
  }, [entries, onEntriesChange]);

  // Delete an entry
  const handleDeleteEntry = useCallback(
    (index: number) => {
      // If we're editing this entry, cancel the edit
      if (editingIndex === index) {
        setEditingIndex(-1);
        setEditText('');
      } else if (editingIndex > index) {
        // Adjust editing index if we deleted an entry before it
        setEditingIndex(editingIndex - 1);
      }
      const newEntries = entries.filter((_, i) => i !== index);
      onEntriesChange(newEntries);
      setOpenMenuIndex(-1);
    },
    [entries, onEntriesChange, editingIndex]
  );

  // Assign user to an entry
  const handleAssignUser = useCallback(
    (index: number, userEmail: string) => {
      const newEntries = [...entries];
      newEntries[index] = {
        ...newEntries[index],
        originalUsername: userEmail,
        isManagerAdded: false,
      };
      onEntriesChange(newEntries);
      setOpenMenuIndex(-1);
      setOpenUserMenuIndex(-1);
    },
    [entries, onEntriesChange]
  );

  // Remove user attribution from an entry
  const handleRemoveUser = useCallback(
    (index: number) => {
      const newEntries = [...entries];
      newEntries[index] = {
        ...newEntries[index],
        originalUsername: undefined,
        originalReportId: undefined,
        isManagerAdded: true,
      };
      onEntriesChange(newEntries);
      setOpenMenuIndex(-1);
    },
    [entries, onEntriesChange]
  );

  // Toggle dropdown menu
  const handleMenuToggle = useCallback((index: number) => {
    setOpenMenuIndex(openMenuIndex === index ? -1 : index);
    setOpenUserMenuIndex(-1);
  }, [openMenuIndex]);

  return (
    <Card isPlain style={{ marginBottom: '1rem' }}>
      <CardTitle>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
          <FlexItem>
            <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ gap: '0.5rem' }}>
              <strong>{projectName}</strong>
              <Label color="blue" isCompact>
                {entries.length} {entries.length === 1 ? 'entry' : 'entries'}
              </Label>
            </Flex>
          </FlexItem>
          {isEditing && (
            <FlexItem>
              <Button
                variant="link"
                icon={<PlusIcon />}
                onClick={handleAddEntry}
                isDisabled={editingIndex >= 0}
                size="sm"
              >
                Add Entry
              </Button>
            </FlexItem>
          )}
        </Flex>
      </CardTitle>
      <CardBody>
        {projectDescription && (
          <p style={{ marginBottom: '0.75rem', color: '#6a6e73', fontStyle: 'italic' }}>
            {projectDescription}
          </p>
        )}

        {/* Entries */}
        <Flex direction={{ default: 'column' }} style={{ gap: '0.5rem' }}>
          {entries.length === 0 ? (
            <FlexItem>
              <p style={{ color: '#6a6e73', fontStyle: 'italic' }}>
                No entries yet. {isEditing && 'Click "Add Entry" to create one.'}
              </p>
            </FlexItem>
          ) : (
            entries.map((entry, index) => (
              <FlexItem key={index}>
                <Flex alignItems={{ default: 'alignItemsCenter' }}>
                  <FlexItem grow={{ default: 'grow' }}>
                    {editingIndex === index ? (
                      // Edit mode - show text input
                      <TextInput
                        ref={inputRef}
                        value={editText}
                        onChange={(_event, value) => setEditText(value)}
                        onKeyDown={handleKeyDown}
                        placeholder={placeholder}
                        aria-label={`Edit entry ${index + 1}`}
                        style={{
                          backgroundColor: entry.isManagerAdded ? 'rgba(0, 150, 150, 0.05)' : undefined,
                        }}
                      />
                    ) : (
                      // View mode - show formatted markdown (clickable if editing enabled)
                      <div
                        onClick={() => isEditing && handleStartEdit(index)}
                        style={{
                          padding: '0.375rem 0.5rem',
                          minHeight: '36px',
                          display: 'flex',
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          gap: '0.5rem',
                          backgroundColor: 'rgba(0, 0, 0, 0.02)',
                          borderRadius: '3px',
                          cursor: isEditing ? 'pointer' : 'default',
                          border: '1px solid transparent',
                          transition: 'border-color 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          if (isEditing) {
                            e.currentTarget.style.borderColor = '#0066cc';
                          }
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = 'transparent';
                        }}
                      >
                        {entry.text ? (
                          <InlineMarkdown>{entry.text}</InlineMarkdown>
                        ) : (
                          <span style={{ color: '#6a6e73', fontStyle: 'italic' }}>{placeholder}</span>
                        )}
                        {/* User attribution badge */}
                        {entry.originalUsername && (
                          <Label color="grey" isCompact icon={<UserIcon />}>
                            {getDisplayName(entry.originalUsername)}
                          </Label>
                        )}
                        {entry.isManagerAdded && !entry.originalUsername && (
                          <Label color="teal" isCompact>
                            Manager
                          </Label>
                        )}
                      </div>
                    )}
                  </FlexItem>

                  {/* Action buttons - only show when editing is enabled */}
                  {isEditing && (
                    editingIndex === index ? (
                      // Edit mode buttons: Save and Cancel
                      <>
                        <FlexItem>
                          <Tooltip content="Save (Enter)">
                            <Button
                              variant="plain"
                              onClick={handleSaveEdit}
                              aria-label="Save edit"
                              style={{ color: '#3e8635' }}
                            >
                              <CheckIcon />
                            </Button>
                          </Tooltip>
                        </FlexItem>
                        <FlexItem>
                          <Tooltip content="Cancel (Escape)">
                            <Button
                              variant="plain"
                              onClick={handleCancelEdit}
                              aria-label="Cancel edit"
                              style={{ color: '#6a6e73' }}
                            >
                              <TimesIcon />
                            </Button>
                          </Tooltip>
                        </FlexItem>
                      </>
                    ) : (
                      // View mode buttons: Edit and 3-dots menu
                      <>
                        <FlexItem>
                          <Tooltip content="Edit entry">
                            <Button
                              variant="plain"
                              onClick={() => handleStartEdit(index)}
                              aria-label="Edit entry"
                              style={{ color: '#0066cc' }}
                            >
                              <PencilAltIcon />
                            </Button>
                          </Tooltip>
                        </FlexItem>
                        <FlexItem>
                          <Dropdown
                            isOpen={openMenuIndex === index}
                            onOpenChange={(isOpen) => {
                              if (!isOpen) {
                                setOpenMenuIndex(-1);
                                setOpenUserMenuIndex(-1);
                              }
                            }}
                            toggle={(toggleRef: React.Ref<MenuToggleElement>) => (
                              <MenuToggle
                                ref={toggleRef}
                                onClick={() => handleMenuToggle(index)}
                                variant="plain"
                                aria-label="Entry actions"
                              >
                                <EllipsisVIcon />
                              </MenuToggle>
                            )}
                            popperProps={{ position: 'right' }}
                          >
                            <DropdownList>
                              {/* Assign to user - show submenu */}
                              <DropdownItem
                                key="assign"
                                onClick={() => setOpenUserMenuIndex(openUserMenuIndex === index ? -1 : index)}
                              >
                                <UserIcon style={{ marginRight: '0.5rem' }} />
                                Assign to user
                              </DropdownItem>
                              
                              {/* User selection submenu */}
                              {openUserMenuIndex === index && teamMembers.length > 0 && (
                                <>
                                  {teamMembers.map((member) => (
                                    <DropdownItem
                                      key={member.email}
                                      onClick={() => handleAssignUser(index, member.email)}
                                      style={{ paddingLeft: '2rem' }}
                                    >
                                      {member.displayName || getDisplayName(member.email)}
                                    </DropdownItem>
                                  ))}
                                </>
                              )}
                              
                              {/* Remove user attribution */}
                              {entry.originalUsername && (
                                <DropdownItem
                                  key="remove-user"
                                  onClick={() => handleRemoveUser(index)}
                                >
                                  <TimesIcon style={{ marginRight: '0.5rem' }} />
                                  Remove user attribution
                                </DropdownItem>
                              )}
                              
                              {/* Delete entry */}
                              <DropdownItem
                                key="delete"
                                onClick={() => handleDeleteEntry(index)}
                                isDanger
                              >
                                <TrashIcon style={{ marginRight: '0.5rem' }} />
                                Delete entry
                              </DropdownItem>
                            </DropdownList>
                          </Dropdown>
                        </FlexItem>
                      </>
                    )
                  )}
                </Flex>
              </FlexItem>
            ))
          )}
        </Flex>
      </CardBody>
    </Card>
  );
}

export default ProjectEntryEditor;

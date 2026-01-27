/**
 * Consolidated User Block Editor - Editor for a user's entries within the consolidated view.
 * Provides the same click-to-edit UX as ReportEntryEditor but adapted for
 * the consolidated report context with user attribution.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Button,
  Card,
  CardBody,
  Flex,
  FlexItem,
  Label,
  TextInput,
  Tooltip,
} from '@patternfly/react-core';
import {
  CheckIcon,
  PencilAltIcon,
  PlusIcon,
  TimesIcon,
  TrashIcon,
  UserIcon,
} from '@patternfly/react-icons';
import { format } from 'date-fns';
import { InlineMarkdown } from '@/components/StyledMarkdown';
import type { ConsolidatedUserEntry } from '@/types';

export interface EditableEntry {
  text: string;
  index: number;  // Original index in user's report (-1 for manager-added)
  isManagerAdded?: boolean;
}

export interface ConsolidatedUserBlockEditorProps {
  /** Username of the report owner */
  username: string;
  /** Report period (e.g., "Week 4, Jan 2026") */
  reportPeriod: string | null;
  /** When the report was created */
  createdAt: string | null;
  /** Report ID */
  reportId: number;
  /** The entries to display/edit */
  entries: ConsolidatedUserEntry[];
  /** Whether editing is enabled */
  isEditing: boolean;
  /** Callback when entries change */
  onEntriesChange: (entries: EditableEntry[]) => void;
  /** Placeholder text for new entries */
  placeholder?: string;
}

/**
 * Get display name from email address
 */
function getDisplayName(email: string): string {
  return email.split('@')[0];
}

/**
 * Convert ConsolidatedUserEntry to EditableEntry for internal state
 */
function toEditableEntries(entries: ConsolidatedUserEntry[]): EditableEntry[] {
  return entries.map((e) => ({
    text: e.text,
    index: e.index,
    isManagerAdded: false,
  }));
}

export function ConsolidatedUserBlockEditor({
  username,
  reportPeriod,
  createdAt,
  reportId: _reportId,  // Used by parent for identification, not used internally
  entries,
  isEditing,
  onEntriesChange,
  placeholder = 'Work item description...',
}: ConsolidatedUserBlockEditorProps) {
  // Convert to editable entries
  const editableEntries = toEditableEntries(entries);
  
  // Track which entry index is being edited (-1 = none)
  const [editingIndex, setEditingIndex] = useState<number>(-1);
  // Temporary text while editing (before save)
  const [editText, setEditText] = useState<string>('');
  // Ref to focus input when editing starts
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset editing state when editing mode is turned off
  useEffect(() => {
    if (!isEditing) {
      setEditingIndex(-1);
      setEditText('');
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
    setEditText(editableEntries[index].text);
  }, [editableEntries, isEditing]);

  // Save the current edit
  const handleSaveEdit = useCallback(() => {
    if (editingIndex >= 0) {
      const newEntries = [...editableEntries];
      newEntries[editingIndex] = { ...newEntries[editingIndex], text: editText };
      onEntriesChange(newEntries);
      setEditingIndex(-1);
      setEditText('');
    }
  }, [editingIndex, editText, editableEntries, onEntriesChange]);

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

  // Add a new entry (manager-added)
  const handleAddEntry = useCallback(() => {
    const newEntries: EditableEntry[] = [
      ...editableEntries, 
      { text: '', index: -1, isManagerAdded: true }
    ];
    onEntriesChange(newEntries);
    // Start editing the new entry
    setEditingIndex(newEntries.length - 1);
    setEditText('');
  }, [editableEntries, onEntriesChange]);

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
      const newEntries = editableEntries.filter((_, i) => i !== index);
      onEntriesChange(newEntries);
    },
    [editableEntries, onEntriesChange, editingIndex]
  );

  return (
    <Card isPlain style={{ marginBottom: '1rem' }}>
      <CardBody>
        {/* User attribution header */}
        <Flex 
          alignItems={{ default: 'alignItemsCenter' }} 
          justifyContent={{ default: 'justifyContentSpaceBetween' }}
          style={{ marginBottom: '0.75rem' }}
        >
          <FlexItem>
            <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ gap: '0.5rem' }}>
              <UserIcon style={{ color: '#6a6e73' }} />
              <strong>{getDisplayName(username)}</strong>
              {reportPeriod && (
                <Label color="grey" isCompact>
                  {reportPeriod}
                </Label>
              )}
            </Flex>
          </FlexItem>
          <FlexItem>
            {createdAt && (
              <small style={{ color: '#6a6e73' }}>
                {format(new Date(createdAt), 'MMM d, yyyy')}
              </small>
            )}
          </FlexItem>
        </Flex>

        {/* Entries */}
        <Flex direction={{ default: 'column' }} style={{ gap: '0.5rem' }}>
          {editableEntries.map((entry, index) => (
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
                        backgroundColor: entry.isManagerAdded ? 'rgba(0, 150, 150, 0.05)' : 'rgba(0, 0, 0, 0.02)',
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
                      {entry.isManagerAdded && (
                        <Label color="teal" isCompact style={{ marginLeft: '0.5rem' }}>
                          Manager Added
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
                    // View mode buttons: Edit, Delete
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
                        <Tooltip content="Delete entry">
                          <Button
                            variant="plain"
                            isDanger
                            onClick={() => handleDeleteEntry(index)}
                            isDisabled={editableEntries.length <= 1}
                            aria-label="Delete entry"
                          >
                            <TrashIcon />
                          </Button>
                        </Tooltip>
                      </FlexItem>
                    </>
                  )
                )}
              </Flex>
            </FlexItem>
          ))}
          
          {/* Add Entry button - only show when editing */}
          {isEditing && (
            <FlexItem>
              <Button
                variant="link"
                icon={<PlusIcon />}
                onClick={handleAddEntry}
                isDisabled={editingIndex >= 0}
              >
                Add Entry
              </Button>
            </FlexItem>
          )}
        </Flex>
      </CardBody>
    </Card>
  );
}

export default ConsolidatedUserBlockEditor;

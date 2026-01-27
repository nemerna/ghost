/**
 * Consolidated Draft Entry Editor - Structured editor for consolidated report draft entries
 * with click-to-edit mode, author attribution, and inline editing.
 * 
 * Similar to ReportEntryEditor but adapted for manager's consolidated draft view:
 * - Shows original author attribution
 * - Visual distinction for manager-added entries
 * - No visibility toggle (not relevant for manager view)
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Button,
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
import { InlineMarkdown } from '@/components/StyledMarkdown';
import type { ConsolidatedDraftEntry } from '@/types';

export interface ConsolidatedDraftEntryEditorProps {
  /** Current entries */
  entries: ConsolidatedDraftEntry[];
  /** Callback when entries change */
  onChange: (entries: ConsolidatedDraftEntry[]) => void;
  /** Placeholder text for new entries */
  placeholder?: string;
  /** Whether the editor is disabled */
  disabled?: boolean;
}

export function ConsolidatedDraftEntryEditor({
  entries,
  onChange,
  placeholder = 'Work item description with links...',
  disabled = false,
}: ConsolidatedDraftEntryEditorProps) {
  // Track which entry index is being edited (-1 = none)
  const [editingIndex, setEditingIndex] = useState<number>(-1);
  // Temporary text while editing (before save)
  const [editText, setEditText] = useState<string>('');
  // Ref to focus input when editing starts
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when editing starts
  useEffect(() => {
    if (editingIndex >= 0 && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editingIndex]);

  // Start editing an entry
  const handleStartEdit = useCallback((index: number) => {
    setEditingIndex(index);
    setEditText(entries[index].text);
  }, [entries]);

  // Save the current edit
  const handleSaveEdit = useCallback(() => {
    if (editingIndex >= 0) {
      const newEntries = [...entries];
      newEntries[editingIndex] = { ...newEntries[editingIndex], text: editText };
      onChange(newEntries);
      setEditingIndex(-1);
      setEditText('');
    }
  }, [editingIndex, editText, entries, onChange]);

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

  // Add a new empty entry (manager-added)
  const handleAddEntry = useCallback(() => {
    const newEntries: ConsolidatedDraftEntry[] = [
      ...entries, 
      { text: '', is_manager_added: true }
    ];
    onChange(newEntries);
    // Start editing the new entry
    setEditingIndex(newEntries.length - 1);
    setEditText('');
  }, [entries, onChange]);

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
      onChange(newEntries);
    },
    [entries, onChange, editingIndex]
  );

  // Get display name from email
  const getDisplayName = (email: string | undefined) => {
    if (!email) return null;
    return email.split('@')[0];
  };

  return (
    <Flex direction={{ default: 'column' }} style={{ gap: '0.75rem' }}>
      {entries.map((entry, index) => (
        <FlexItem key={index}>
          {/* Author attribution row */}
          <Flex 
            alignItems={{ default: 'alignItemsCenter' }} 
            style={{ marginBottom: '0.25rem' }}
          >
            <FlexItem>
              {entry.original_username ? (
                <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ gap: '0.25rem' }}>
                  <UserIcon style={{ color: '#6a6e73', fontSize: '0.75rem' }} />
                  <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>
                    {getDisplayName(entry.original_username)}
                  </span>
                  {entry.is_manager_added && (
                    <Label color="teal" isCompact style={{ marginLeft: '0.25rem' }}>
                      Modified
                    </Label>
                  )}
                </Flex>
              ) : (
                <Label color="teal" isCompact>
                  Manager Added
                </Label>
              )}
            </FlexItem>
          </Flex>

          {/* Entry content row */}
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
                  isDisabled={disabled}
                  aria-label={`Edit entry ${index + 1}`}
                  style={{
                    backgroundColor: entry.is_manager_added && !entry.original_username 
                      ? 'rgba(0, 150, 150, 0.05)' 
                      : undefined,
                  }}
                />
              ) : (
                // View mode - show formatted markdown
                <div
                  onClick={() => !disabled && handleStartEdit(index)}
                  style={{
                    padding: '0.375rem 0.5rem',
                    minHeight: '36px',
                    display: 'flex',
                    alignItems: 'center',
                    backgroundColor: entry.is_manager_added && !entry.original_username 
                      ? 'rgba(0, 150, 150, 0.05)' 
                      : 'rgba(0, 0, 0, 0.02)',
                    borderRadius: '3px',
                    cursor: disabled ? 'default' : 'pointer',
                    border: '1px solid transparent',
                    transition: 'border-color 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!disabled) {
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
                </div>
              )}
            </FlexItem>
            
            {/* Action buttons */}
            {editingIndex === index ? (
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
                      isDisabled={disabled}
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
                      isDisabled={disabled || entries.length <= 1}
                      aria-label="Delete entry"
                    >
                      <TrashIcon />
                    </Button>
                  </Tooltip>
                </FlexItem>
              </>
            )}
          </Flex>
        </FlexItem>
      ))}
      <FlexItem>
        <Button
          variant="link"
          icon={<PlusIcon />}
          onClick={handleAddEntry}
          isDisabled={disabled || editingIndex >= 0}
        >
          Add Entry
        </Button>
      </FlexItem>
    </Flex>
  );
}

export default ConsolidatedDraftEntryEditor;

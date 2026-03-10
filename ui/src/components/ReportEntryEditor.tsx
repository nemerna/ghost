/**
 * Report Entry Editor - Structured editor for management report entries
 * with per-entry visibility toggles and inline editing.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Button,
  Flex,
  FlexItem,
  TextInput,
  Tooltip,
} from '@patternfly/react-core';
import {
  CheckIcon,
  EyeIcon,
  LockIcon,
  PencilAltIcon,
  PlusIcon,
  TimesIcon,
  TrashIcon,
} from '@patternfly/react-icons';
import { InlineMarkdown } from '@/components/StyledMarkdown';
import type { ReportEntry, ReportEntryInput } from '@/types';

export interface ReportEntryEditorProps {
  /** Current entries */
  entries: ReportEntryInput[];
  /** Callback when entries change */
  onChange: (entries: ReportEntryInput[]) => void;
  /** Placeholder text for new entries */
  placeholder?: string;
  /** Whether the editor is disabled */
  disabled?: boolean;
}

/**
 * Convert backend ReportEntry to editable ReportEntryInput.
 */
export function reportEntriesToInputs(entries: ReportEntry[] | null | undefined): ReportEntryInput[] {
  if (!entries) return [];
  return entries.map((e) => ({ text: e.text, private: e.private, ticket_key: e.ticket_key ?? undefined }));
}

export function ReportEntryEditor({
  entries,
  onChange,
  placeholder = 'Work item description with links...',
  disabled = false,
}: ReportEntryEditorProps) {
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

  // Add a new empty entry (and start editing it)
  const handleAddEntry = useCallback(() => {
    const newEntries = [...entries, { text: '', private: false }];
    onChange(newEntries);
    // Start editing the new entry
    setEditingIndex(newEntries.length - 1);
    setEditText('');
  }, [entries, onChange]);

  // Toggle an entry's visibility
  const handleToggleVisibility = useCallback(
    (index: number) => {
      const newEntries = [...entries];
      newEntries[index] = {
        ...newEntries[index],
        private: !newEntries[index].private,
      };
      onChange(newEntries);
    },
    [entries, onChange]
  );

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

  return (
    <Flex direction={{ default: 'column' }} style={{ gap: '0.5rem' }}>
      {entries.map((entry, index) => (
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
                  isDisabled={disabled}
                  aria-label={`Edit entry ${index + 1}`}
                  style={{
                    backgroundColor: entry.private ? 'rgba(255, 0, 0, 0.05)' : undefined,
                  }}
                />
              ) : (
                // View mode - show formatted markdown
                <div
                  style={{
                    padding: '0.375rem 0.5rem',
                    minHeight: '36px',
                    display: 'flex',
                    alignItems: 'center',
                    backgroundColor: entry.private ? 'rgba(255, 0, 0, 0.05)' : 'rgba(0, 0, 0, 0.02)',
                    borderRadius: '3px',
                    color: entry.private ? '#6a6e73' : 'inherit',
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
                  <Tooltip content="Save">
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
                  <Tooltip content="Cancel">
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
              // View mode buttons: Edit, Visibility, Delete
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
                  <Tooltip
                    content={
                      entry.private
                        ? 'Private - hidden from manager (click to share)'
                        : 'Shared - visible to manager (click to hide)'
                    }
                  >
                    <Button
                      variant="plain"
                      onClick={() => handleToggleVisibility(index)}
                      isDisabled={disabled}
                      aria-label={entry.private ? 'Make visible' : 'Make private'}
                      style={{ color: entry.private ? '#c9190b' : '#3e8635' }}
                    >
                      {entry.private ? <LockIcon /> : <EyeIcon />}
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

export default ReportEntryEditor;

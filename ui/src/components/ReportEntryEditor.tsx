/**
 * Report Entry Editor - Structured editor for management report entries
 * with per-entry visibility toggles.
 */

import { useCallback } from 'react';
import {
  Button,
  Flex,
  FlexItem,
  TextInput,
  Tooltip,
} from '@patternfly/react-core';
import {
  EyeIcon,
  LockIcon,
  PlusIcon,
  TrashIcon,
} from '@patternfly/react-icons';
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
  return entries.map((e) => ({ text: e.text, private: e.private }));
}

export function ReportEntryEditor({
  entries,
  onChange,
  placeholder = 'Work item description with links...',
  disabled = false,
}: ReportEntryEditorProps) {
  // Add a new empty entry
  const handleAddEntry = useCallback(() => {
    onChange([...entries, { text: '', private: false }]);
  }, [entries, onChange]);

  // Update an entry's text
  const handleTextChange = useCallback(
    (index: number, text: string) => {
      const newEntries = [...entries];
      newEntries[index] = { ...newEntries[index], text };
      onChange(newEntries);
    },
    [entries, onChange]
  );

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
      const newEntries = entries.filter((_, i) => i !== index);
      onChange(newEntries);
    },
    [entries, onChange]
  );

  return (
    <Flex direction={{ default: 'column' }} style={{ gap: '0.5rem' }}>
      {entries.map((entry, index) => (
        <FlexItem key={index}>
          <Flex alignItems={{ default: 'alignItemsCenter' }}>
            <FlexItem grow={{ default: 'grow' }}>
              <TextInput
                value={entry.text}
                onChange={(_event, value) => handleTextChange(index, value)}
                placeholder={placeholder}
                isDisabled={disabled}
                aria-label={`Entry ${index + 1}`}
                style={{
                  backgroundColor: entry.private ? 'rgba(255, 0, 0, 0.05)' : undefined,
                }}
              />
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
          </Flex>
        </FlexItem>
      ))}
      <FlexItem>
        <Button
          variant="link"
          icon={<PlusIcon />}
          onClick={handleAddEntry}
          isDisabled={disabled}
        >
          Add Entry
        </Button>
      </FlexItem>
    </Flex>
  );
}

export default ReportEntryEditor;

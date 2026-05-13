/**
 * Report Entry Editor - Structured editor for management report entries.
 * Displays entries as a compact table with per-row actions (3-dot menu).
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
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
  ActionsColumn,
} from '@patternfly/react-table';
import {
  CheckIcon,
  EyeIcon,
  LockIcon,
  PlusIcon,
  TimesIcon,
} from '@patternfly/react-icons';
import { ExternalLinkAltIcon } from '@patternfly/react-icons';
import { InlineMarkdown } from '@/components/StyledMarkdown';
import { ProjectBadge } from '@/components/ProjectBadge';
import type { ReportEntry, ReportEntryInput, ReportField } from '@/types';

function buildTicketUrl(ticketKey: string, jiraServerUrl?: string, entryText?: string): string | null {
  // GitHub: org/repo#123 → GitHub issues URL
  const githubMatch = ticketKey.match(/^([^#]+)#(\d+)$/);
  if (githubMatch) {
    const [, repo, num] = githubMatch;
    return `https://github.com/${repo}/issues/${num}`;
  }

  // Jira: extract URL from embedded markdown in the entry text first (works for old reports)
  if (entryText) {
    const urlPattern = new RegExp(`https?://[^\\s)>"]+/browse/${ticketKey}(?=[\\s)>"<]|$)`, 'i');
    const match = entryText.match(urlPattern);
    if (match) return match[0];
  }

  // Jira: fallback to constructing from jira_server_url preference
  const baseUrl = jiraServerUrl?.replace(/\/+$/, '');
  if (baseUrl && /^[A-Z]+-\d+$/.test(ticketKey)) {
    return `${baseUrl}/browse/${ticketKey}`;
  }

  return null;
}

export interface ReportEntryEditorProps {
  entries: ReportEntryInput[];
  onChange: (entries: ReportEntryInput[]) => void;
  placeholder?: string;
  disabled?: boolean;
  fields?: ReportField[];
  jiraServerUrl?: string;
}

export function reportEntriesToInputs(entries: ReportEntry[] | null | undefined): ReportEntryInput[] {
  if (!entries) return [];
  return entries.map((e) => ({
    text: e.text,
    private: e.private,
    ticket_key: e.ticket_key ?? undefined,
    detected_project_id: e.detected_project_id ?? undefined,
  }));
}

export function ReportEntryEditor({
  entries,
  onChange,
  placeholder = 'Work item description with links...',
  disabled = false,
  fields,
  jiraServerUrl,
}: ReportEntryEditorProps) {
  const [editingIndex, setEditingIndex] = useState<number>(-1);
  const [editText, setEditText] = useState('');
  const [editTicketKey, setEditTicketKey] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingIndex >= 0 && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editingIndex]);

  const handleStartEdit = useCallback((index: number) => {
    setEditingIndex(index);
    setEditText(entries[index].text);
    setEditTicketKey(entries[index].ticket_key ?? '');
  }, [entries]);

  const handleSaveEdit = useCallback(() => {
    if (editingIndex >= 0) {
      const newEntries = [...entries];
      newEntries[editingIndex] = {
        ...newEntries[editingIndex],
        text: editText,
        ticket_key: editTicketKey.trim() || undefined,
      };
      onChange(newEntries);
      setEditingIndex(-1);
      setEditText('');
      setEditTicketKey('');
    }
  }, [editingIndex, editText, editTicketKey, entries, onChange]);

  const handleCancelEdit = useCallback(() => {
    setEditingIndex(-1);
    setEditText('');
    setEditTicketKey('');
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); handleSaveEdit(); }
    else if (e.key === 'Escape') { handleCancelEdit(); }
  }, [handleSaveEdit, handleCancelEdit]);

  const handleAddEntry = useCallback(() => {
    const newEntries = [...entries, { text: '', private: false }];
    onChange(newEntries);
    setEditingIndex(newEntries.length - 1);
    setEditText('');
    setEditTicketKey('');
  }, [entries, onChange]);

  const handleToggleVisibility = useCallback((index: number) => {
    const newEntries = [...entries];
    newEntries[index] = { ...newEntries[index], private: !newEntries[index].private };
    onChange(newEntries);
  }, [entries, onChange]);

  const handleDeleteEntry = useCallback((index: number) => {
    if (editingIndex === index) { setEditingIndex(-1); setEditText(''); setEditTicketKey(''); }
    else if (editingIndex > index) { setEditingIndex(editingIndex - 1); }
    onChange(entries.filter((_, i) => i !== index));
  }, [entries, onChange, editingIndex]);

  const handleProjectChange = useCallback((index: number, projectId: number | null) => {
    const newEntries = [...entries];
    newEntries[index] = { ...newEntries[index], detected_project_id: projectId };
    onChange(newEntries);
  }, [entries, onChange]);

  return (
    <>
      <Table aria-label="Report entries" variant="compact">
        <Thead>
          <Tr>
            <Th>Entry</Th>
            <Th width={15}>Ticket</Th>
            <Th width={15}>Project</Th>
            <Th width={10}>Visibility</Th>
            <Th screenReaderText="Actions" />
          </Tr>
        </Thead>
        <Tbody>
          {entries.map((entry, index) => {
            const isEditing = editingIndex === index;

            if (isEditing) {
              return (
                <Tr key={index} style={{ backgroundColor: 'var(--pf-t--global--background--color--secondary--default)' }}>
                  <Td colSpan={3}>
                    <Flex direction={{ default: 'column' }} style={{ gap: '0.25rem' }}>
                      <FlexItem>
                        <TextInput
                          ref={inputRef}
                          value={editText}
                          onChange={(_e, v) => setEditText(v)}
                          onKeyDown={handleKeyDown}
                          placeholder={placeholder}
                          isDisabled={disabled}
                          aria-label={`Edit entry ${index + 1}`}
                        />
                      </FlexItem>
                      <FlexItem>
                        <TextInput
                          value={editTicketKey}
                          onChange={(_e, v) => setEditTicketKey(v)}
                          onKeyDown={handleKeyDown}
                          placeholder="Ticket key e.g. PROJ-123"
                          isDisabled={disabled}
                          aria-label={`Ticket key for entry ${index + 1}`}
                          style={{ fontSize: '0.8rem', height: '28px' }}
                        />
                      </FlexItem>
                    </Flex>
                  </Td>
                  <Td colSpan={2}>
                    <Flex style={{ gap: '0.25rem' }}>
                      <FlexItem>
                        <Tooltip content="Save (Enter)">
                          <Button variant="plain" onClick={handleSaveEdit} aria-label="Save" style={{ color: '#3e8635' }}>
                            <CheckIcon />
                          </Button>
                        </Tooltip>
                      </FlexItem>
                      <FlexItem>
                        <Tooltip content="Cancel (Esc)">
                          <Button variant="plain" onClick={handleCancelEdit} aria-label="Cancel" style={{ color: '#6a6e73' }}>
                            <TimesIcon />
                          </Button>
                        </Tooltip>
                      </FlexItem>
                    </Flex>
                  </Td>
                </Tr>
              );
            }

            return (
              <Tr key={index} style={entry.private ? { opacity: 0.75 } : undefined}>
                <Td dataLabel="Entry">
                  {entry.text
                    ? <InlineMarkdown>{entry.text}</InlineMarkdown>
                    : <span style={{ color: '#6a6e73', fontStyle: 'italic' }}>{placeholder}</span>}
                </Td>
                <Td dataLabel="Ticket" modifier="nowrap">
                  {entry.ticket_key ? (() => {
                    const url = buildTicketUrl(entry.ticket_key, jiraServerUrl, entry.text);
                    return url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}>
                        <Label color="blue" isCompact style={{ cursor: 'pointer' }}>
                          {entry.ticket_key}
                        </Label>
                        <ExternalLinkAltIcon style={{ fontSize: '0.7em', color: '#6a6e73' }} />
                      </a>
                    ) : (
                      <Label color="blue" isCompact>{entry.ticket_key}</Label>
                    );
                  })() : <span style={{ color: '#6a6e73' }}>—</span>}
                </Td>
                <Td dataLabel="Project">
                  {fields && fields.length > 0
                    ? <ProjectBadge
                        projectId={entry.detected_project_id ?? null}
                        fields={fields}
                        onChange={(pid) => handleProjectChange(index, pid)}
                        disabled={disabled}
                      />
                    : <span style={{ color: '#6a6e73' }}>—</span>}
                </Td>
                <Td dataLabel="Visibility">
                  <Tooltip content={entry.private ? 'Private — click to share' : 'Shared — click to hide'}>
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
                </Td>
                <Td isActionCell>
                  <ActionsColumn
                    items={[
                      {
                        title: 'Edit',
                        onClick: () => handleStartEdit(index),
                        isDisabled: disabled || editingIndex >= 0,
                      },
                      {
                        title: 'Delete',
                        onClick: () => handleDeleteEntry(index),
                        isDisabled: disabled || entries.length <= 1,
                      },
                    ]}
                  />
                </Td>
              </Tr>
            );
          })}
        </Tbody>
      </Table>
      <Button
        variant="link"
        icon={<PlusIcon />}
        onClick={handleAddEntry}
        isDisabled={disabled || editingIndex >= 0}
        style={{ marginTop: '0.5rem' }}
      >
        Add Entry
      </Button>
    </>
  );
}

export default ReportEntryEditor;

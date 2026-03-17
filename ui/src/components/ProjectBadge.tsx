/**
 * ProjectBadge - Compact inline badge showing the detected field/project
 * for a report entry, with a dropdown selector for manual assignment.
 */

import { useState, useMemo, useCallback } from 'react';
import {
  Label,
  MenuToggle,
  Select,
  SelectGroup,
  SelectList,
  SelectOption,
} from '@patternfly/react-core';
import { FolderOpenIcon } from '@patternfly/react-icons';
import type { ReportField, ReportProject } from '@/types';

export interface ProjectBadgeProps {
  projectId: number | null | undefined;
  fields: ReportField[];
  onChange: (projectId: number | null) => void;
  disabled?: boolean;
}

interface FlatLeaf {
  projectId: number;
  label: string;
  fieldName: string;
}

function collectLeaves(
  projects: ReportProject[],
  fieldName: string,
  parentPath: string[] = [],
): FlatLeaf[] {
  const result: FlatLeaf[] = [];
  for (const p of projects) {
    const path = [...parentPath, p.name];
    if (p.children.length === 0) {
      result.push({ projectId: p.id, label: path.join(' > '), fieldName });
    } else {
      result.push(...collectLeaves(p.children, fieldName, path));
    }
  }
  return result;
}

function findProjectPath(
  fields: ReportField[],
  projectId: number,
): { fieldName: string; path: string } | null {
  for (const field of fields) {
    const found = searchTree(field.projects, projectId, []);
    if (found) return { fieldName: field.name, path: found.join(' > ') };
  }
  return null;
}

function searchTree(
  projects: ReportProject[],
  targetId: number,
  trail: string[],
): string[] | null {
  for (const p of projects) {
    const current = [...trail, p.name];
    if (p.id === targetId) return current;
    if (p.children.length > 0) {
      const r = searchTree(p.children, targetId, current);
      if (r) return r;
    }
  }
  return null;
}

export function ProjectBadge({
  projectId,
  fields,
  onChange,
  disabled = false,
}: ProjectBadgeProps) {
  const [isOpen, setIsOpen] = useState(false);

  const resolved = useMemo(() => {
    if (!projectId || !fields.length) return null;
    return findProjectPath(fields, projectId);
  }, [projectId, fields]);

  const groups = useMemo(
    () =>
      fields
        .map((f) => ({
          fieldId: f.id,
          fieldName: f.name,
          leaves: collectLeaves(f.projects, f.name),
        }))
        .filter((g) => g.leaves.length > 0),
    [fields],
  );

  const handleSelect = useCallback(
    (_e: React.MouseEvent | undefined, value: string | number | undefined) => {
      if (typeof value === 'number') onChange(value);
      setIsOpen(false);
    },
    [onChange],
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange(null);
    },
    [onChange],
  );

  if (!fields.length) return null;

  const selectBody = groups.map((group) => (
    <SelectGroup key={group.fieldId} label={group.fieldName}>
      <SelectList>
        {group.leaves.map((leaf) => (
          <SelectOption
            key={leaf.projectId}
            value={leaf.projectId}
            isSelected={leaf.projectId === projectId}
          >
            {leaf.label}
          </SelectOption>
        ))}
      </SelectList>
    </SelectGroup>
  ));

  return (
    <div style={{ marginTop: '0.25rem' }}>
      <Select
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        onSelect={handleSelect}
        toggle={(toggleRef) =>
          resolved ? (
            <MenuToggle
              ref={toggleRef}
              variant="plainText"
              onClick={() => setIsOpen((o) => !o)}
              isExpanded={isOpen}
              isDisabled={disabled}
              style={{ padding: 0, minWidth: 0, border: 'none', background: 'none' }}
            >
              <Label
                color="blue"
                isCompact
                icon={<FolderOpenIcon />}
                onClose={disabled ? undefined : handleClear}
                style={{ cursor: disabled ? 'default' : 'pointer' }}
              >
                {resolved.fieldName} &rsaquo; {resolved.path}
              </Label>
            </MenuToggle>
          ) : (
            <MenuToggle
              ref={toggleRef}
              variant="plainText"
              onClick={() => setIsOpen((o) => !o)}
              isExpanded={isOpen}
              isDisabled={disabled}
              style={{
                fontSize: '0.8rem',
                color: '#6a6e73',
                padding: '0 0.375rem',
                minHeight: 'auto',
              }}
            >
              <FolderOpenIcon style={{ marginRight: '0.25rem' }} />
              Assign project
            </MenuToggle>
          )
        }
      >
        {selectBody}
      </Select>
    </div>
  );
}

export default ProjectBadge;

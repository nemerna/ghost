/**
 * Email Templates Modal - Manage email distribution templates
 * Allows managers to create/edit templates that define:
 * - Recipients list
 * - Subject template with placeholders
 * - Which fields/projects to include in the report
 */

import { useState, useEffect, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Divider,
  Form,
  FormGroup,
  FormHelperText,
  HelperText,
  HelperTextItem,
  Label,
  LabelGroup,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Select,
  SelectList,
  SelectOption,
  MenuToggle,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { PlusIcon, TrashIcon, PencilAltIcon } from '@patternfly/react-icons';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td,
} from '@patternfly/react-table';
import {
  listEmailTemplates,
  createEmailTemplate,
  updateEmailTemplate,
  deleteEmailTemplate,
} from '@/api/users';
import { listFields } from '@/api/fields';
import type {
  EmailDistributionTemplate,
  EmailTemplateCreateRequest,
} from '@/types';

interface EmailTemplatesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type EditMode = 'list' | 'create' | 'edit';

export function EmailTemplatesModal({ isOpen, onClose }: EmailTemplatesModalProps) {
  const queryClient = useQueryClient();
  
  // State
  const [mode, setMode] = useState<EditMode>('list');
  const [selectedTemplate, setSelectedTemplate] = useState<EmailDistributionTemplate | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [name, setName] = useState('');
  const [recipientsInput, setRecipientsInput] = useState('');
  const [recipients, setRecipients] = useState<string[]>([]);
  const [subjectTemplate, setSubjectTemplate] = useState('');
  const [selectedFieldIds, setSelectedFieldIds] = useState<number[]>([]);
  const [selectedProjectIds, setSelectedProjectIds] = useState<number[]>([]);
  
  // Field/project selection dropdowns
  const [fieldSelectOpen, setFieldSelectOpen] = useState(false);
  const [projectSelectOpen, setProjectSelectOpen] = useState(false);
  
  // Fetch templates
  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['emailTemplates'],
    queryFn: listEmailTemplates,
    enabled: isOpen,
  });
  
  // Fetch fields for selection
  const { data: fieldsData } = useQuery({
    queryKey: ['fields'],
    queryFn: listFields,
    enabled: isOpen,
  });
  
  // Get available projects based on selected fields
  const availableProjects = useMemo(() => {
    if (!fieldsData?.fields) return [];
    
    // If no fields selected, show all projects
    if (selectedFieldIds.length === 0) {
      return fieldsData.fields.flatMap(f => 
        f.projects.map(p => ({ ...p, fieldName: f.name }))
      );
    }
    
    // Show projects from selected fields only
    return fieldsData.fields
      .filter(f => selectedFieldIds.includes(f.id))
      .flatMap(f => f.projects.map(p => ({ ...p, fieldName: f.name })));
  }, [fieldsData, selectedFieldIds]);
  
  // Mutations
  const createMutation = useMutation({
    mutationFn: createEmailTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emailTemplates'] });
      setMode('list');
      resetForm();
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });
  
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: EmailTemplateCreateRequest }) =>
      updateEmailTemplate(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emailTemplates'] });
      setMode('list');
      resetForm();
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });
  
  const deleteMutation = useMutation({
    mutationFn: deleteEmailTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emailTemplates'] });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });
  
  // Reset form
  const resetForm = () => {
    setName('');
    setRecipientsInput('');
    setRecipients([]);
    setSubjectTemplate('{{team_name}} - Weekly Report - {{period}}');
    setSelectedFieldIds([]);
    setSelectedProjectIds([]);
    setSelectedTemplate(null);
    setError(null);
  };
  
  // Load template into form for editing
  const loadTemplate = (template: EmailDistributionTemplate) => {
    setSelectedTemplate(template);
    setName(template.name);
    setRecipients(template.recipients);
    setSubjectTemplate(template.subject_template);
    setSelectedFieldIds(template.included_field_ids);
    setSelectedProjectIds(template.included_project_ids);
    setMode('edit');
    setError(null);
  };
  
  // Handle recipient add
  const addRecipient = () => {
    const email = recipientsInput.trim();
    if (email && email.includes('@') && !recipients.includes(email)) {
      setRecipients([...recipients, email]);
      setRecipientsInput('');
    }
  };
  
  // Handle recipient remove
  const removeRecipient = (email: string) => {
    setRecipients(recipients.filter(r => r !== email));
  };
  
  // Handle form submit
  const handleSubmit = () => {
    if (!name.trim()) {
      setError('Template name is required');
      return;
    }
    if (recipients.length === 0) {
      setError('At least one recipient is required');
      return;
    }
    if (!subjectTemplate.trim()) {
      setError('Subject template is required');
      return;
    }
    
    const data: EmailTemplateCreateRequest = {
      name: name.trim(),
      recipients,
      subject_template: subjectTemplate.trim(),
      included_field_ids: selectedFieldIds,
      included_project_ids: selectedProjectIds,
    };
    
    if (mode === 'edit' && selectedTemplate) {
      updateMutation.mutate({ id: selectedTemplate.id, data });
    } else {
      createMutation.mutate(data);
    }
  };
  
  // Handle delete
  const handleDelete = (template: EmailDistributionTemplate) => {
    if (confirm(`Are you sure you want to delete "${template.name}"?`)) {
      deleteMutation.mutate(template.id);
    }
  };
  
  // Handle field selection
  const handleFieldSelect = (fieldId: number) => {
    if (selectedFieldIds.includes(fieldId)) {
      setSelectedFieldIds(selectedFieldIds.filter(id => id !== fieldId));
      // Also remove projects that belong to this field
      const fieldProjects = fieldsData?.fields
        .find(f => f.id === fieldId)?.projects.map(p => p.id) || [];
      setSelectedProjectIds(selectedProjectIds.filter(id => !fieldProjects.includes(id)));
    } else {
      setSelectedFieldIds([...selectedFieldIds, fieldId]);
    }
  };
  
  // Handle project selection
  const handleProjectSelect = (projectId: number) => {
    if (selectedProjectIds.includes(projectId)) {
      setSelectedProjectIds(selectedProjectIds.filter(id => id !== projectId));
    } else {
      setSelectedProjectIds([...selectedProjectIds, projectId]);
    }
  };
  
  // Reset when modal closes
  useEffect(() => {
    if (!isOpen) {
      setMode('list');
      resetForm();
    }
  }, [isOpen]);
  
  // Render list view
  const renderList = () => (
    <>
      <ModalBody>
        {error && (
          <Alert variant="danger" title={error} isInline style={{ marginBottom: '1rem' }} />
        )}
        
        {templatesLoading ? (
          <p>Loading templates...</p>
        ) : !templatesData?.templates.length ? (
          <p>No email templates yet. Create one to get started.</p>
        ) : (
          <Table aria-label="Email templates" variant="compact">
            <Thead>
              <Tr>
                <Th width={25}>Name</Th>
                <Th width={30}>Recipients</Th>
                <Th width={25}>Filter</Th>
                <Th width={20}>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {templatesData.templates.map((template) => (
                <Tr key={template.id}>
                  <Td dataLabel="Name">{template.name}</Td>
                  <Td dataLabel="Recipients">
                    {template.recipients.slice(0, 2).join(', ')}
                    {template.recipients.length > 2 && ` +${template.recipients.length - 2} more`}
                  </Td>
                  <Td dataLabel="Filter">
                    {template.included_field_ids.length === 0 && template.included_project_ids.length === 0
                      ? 'Full Report'
                      : `${template.included_field_ids.length} fields, ${template.included_project_ids.length} projects`}
                  </Td>
                  <Td dataLabel="Actions">
                    <Button
                      variant="plain"
                      onClick={() => loadTemplate(template)}
                      icon={<PencilAltIcon />}
                      aria-label="Edit template"
                    />
                    <Button
                      variant="plain"
                      isDanger
                      onClick={() => handleDelete(template)}
                      icon={<TrashIcon />}
                      aria-label="Delete template"
                      isLoading={deleteMutation.isPending}
                    />
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        )}
      </ModalBody>
      <ModalFooter>
        <Button
          variant="primary"
          icon={<PlusIcon />}
          onClick={() => {
            resetForm();
            setMode('create');
          }}
        >
          Create Template
        </Button>
        <Button variant="link" onClick={onClose}>
          Close
        </Button>
      </ModalFooter>
    </>
  );
  
  // Render create/edit form
  const renderForm = () => (
    <>
      <ModalBody>
        {error && (
          <Alert variant="danger" title={error} isInline style={{ marginBottom: '1rem' }} />
        )}
        
        <Form>
          <FormGroup label="Template Name" isRequired fieldId="template-name">
            <TextInput
              isRequired
              id="template-name"
              value={name}
              onChange={(_e, val) => setName(val)}
              placeholder="e.g., Platform Team Weekly"
            />
          </FormGroup>
          
          <FormGroup label="Recipients" isRequired fieldId="recipients">
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <TextInput
                id="recipients-input"
                value={recipientsInput}
                onChange={(_e, val) => setRecipientsInput(val)}
                placeholder="email@example.com"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addRecipient();
                  }
                }}
                style={{ flex: 1 }}
              />
              <Button variant="secondary" onClick={addRecipient}>
                Add
              </Button>
            </div>
            {recipients.length > 0 && (
              <LabelGroup categoryName="Recipients">
                {recipients.map((email) => (
                  <Label key={email} onClose={() => removeRecipient(email)}>
                    {email}
                  </Label>
                ))}
              </LabelGroup>
            )}
            <FormHelperText>
              <HelperText>
                <HelperTextItem>Press Enter or click Add to add each recipient</HelperTextItem>
              </HelperText>
            </FormHelperText>
          </FormGroup>
          
          <FormGroup label="Subject Template" isRequired fieldId="subject-template">
            <TextInput
              isRequired
              id="subject-template"
              value={subjectTemplate}
              onChange={(_e, val) => setSubjectTemplate(val)}
              placeholder="{{team_name}} - Weekly Report - {{period}}"
            />
            <FormHelperText>
              <HelperText>
                <HelperTextItem>
                  Available placeholders: {'{{team_name}}'}, {'{{period}}'}, {'{{date}}'}
                </HelperTextItem>
              </HelperText>
            </FormHelperText>
          </FormGroup>
          
          <Divider style={{ margin: '1rem 0' }} />
          
          <Title headingLevel="h4" style={{ marginBottom: '0.5rem' }}>
            Report Content Filter
          </Title>
          <p style={{ marginBottom: '1rem', color: '#6a6e73' }}>
            Select which fields and projects to include. Leave empty to send the full report.
          </p>
          
          <FormGroup label="Include Fields" fieldId="field-select">
            <Select
              id="field-select"
              isOpen={fieldSelectOpen}
              onOpenChange={(open) => setFieldSelectOpen(open)}
              toggle={(toggleRef) => (
                <MenuToggle
                  ref={toggleRef}
                  onClick={() => setFieldSelectOpen(!fieldSelectOpen)}
                  isExpanded={fieldSelectOpen}
                  style={{ width: '100%' }}
                >
                  {selectedFieldIds.length === 0
                    ? 'All Fields (no filter)'
                    : `${selectedFieldIds.length} field(s) selected`}
                </MenuToggle>
              )}
              onSelect={(_e, value) => {
                handleFieldSelect(value as number);
              }}
            >
              <SelectList>
                {fieldsData?.fields.map((field) => (
                  <SelectOption
                    key={field.id}
                    value={field.id}
                    hasCheckbox
                    isSelected={selectedFieldIds.includes(field.id)}
                  >
                    {field.name}
                  </SelectOption>
                ))}
              </SelectList>
            </Select>
          </FormGroup>
          
          <FormGroup label="Include Projects" fieldId="project-select">
            <Select
              id="project-select"
              isOpen={projectSelectOpen}
              onOpenChange={(open) => setProjectSelectOpen(open)}
              toggle={(toggleRef) => (
                <MenuToggle
                  ref={toggleRef}
                  onClick={() => setProjectSelectOpen(!projectSelectOpen)}
                  isExpanded={projectSelectOpen}
                  style={{ width: '100%' }}
                  isDisabled={availableProjects.length === 0}
                >
                  {selectedProjectIds.length === 0
                    ? 'All Projects (no filter)'
                    : `${selectedProjectIds.length} project(s) selected`}
                </MenuToggle>
              )}
              onSelect={(_e, value) => {
                handleProjectSelect(value as number);
              }}
            >
              <SelectList>
                {availableProjects.map((project) => (
                  <SelectOption
                    key={project.id}
                    value={project.id}
                    hasCheckbox
                    isSelected={selectedProjectIds.includes(project.id)}
                    description={project.fieldName}
                  >
                    {project.name}
                  </SelectOption>
                ))}
              </SelectList>
            </Select>
          </FormGroup>
        </Form>
      </ModalBody>
      <ModalFooter>
        <Button
          variant="primary"
          onClick={handleSubmit}
          isLoading={createMutation.isPending || updateMutation.isPending}
        >
          {mode === 'edit' ? 'Save Changes' : 'Create Template'}
        </Button>
        <Button
          variant="link"
          onClick={() => {
            setMode('list');
            resetForm();
          }}
        >
          Cancel
        </Button>
      </ModalFooter>
    </>
  );
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      aria-labelledby="email-templates-modal"
      variant="medium"
    >
      <ModalHeader
        title={
          mode === 'list'
            ? 'Email Distribution Templates'
            : mode === 'create'
              ? 'Create Email Template'
              : 'Edit Email Template'
        }
        labelId="email-templates-modal"
      />
      {mode === 'list' ? renderList() : renderForm()}
    </Modal>
  );
}

export default EmailTemplatesModal;

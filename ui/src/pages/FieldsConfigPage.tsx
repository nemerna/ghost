/**
 * Fields Configuration page - manage report fields and projects (admin only)
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardTitle,
  Content,
  ExpandableSection,
  Flex,
  FlexItem,
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
  PageSection,
  Spinner,
  TextArea,
  TextInput,
  Title,
} from '@patternfly/react-core';
import {
  PlusIcon,
  TrashIcon,
  EditAltIcon,
  CubesIcon,
  CodeBranchIcon,
  SyncAltIcon,
} from '@patternfly/react-icons';
import {
  listFields,
  createField,
  updateField,
  deleteField,
  createProject,
  updateProject,
  deleteProject,
  redetectActivities,
} from '@/api/fields';
import type {
  FieldCreateRequest,
  JiraComponentConfig,
  ProjectCreateRequest,
  ReportField,
  ReportProject,
} from '@/types';

export function FieldsConfigPage() {
  const queryClient = useQueryClient();

  // Modal state
  const [isFieldModalOpen, setIsFieldModalOpen] = useState(false);
  const [isProjectModalOpen, setIsProjectModalOpen] = useState(false);
  const [editingField, setEditingField] = useState<ReportField | null>(null);
  const [editingProject, setEditingProject] = useState<ReportProject | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null);
  const [selectedParentId, setSelectedParentId] = useState<number | null>(null);
  
  // Redetect state
  const [redetectResult, setRedetectResult] = useState<string | null>(null);

  // Form state
  const [fieldForm, setFieldForm] = useState<FieldCreateRequest>({ name: '', description: '' });
  const [projectForm, setProjectForm] = useState<ProjectCreateRequest>({
    name: '',
    description: '',
    parent_id: null,
    git_repos: [],
    jira_components: [],
  });
  const [newGitRepo, setNewGitRepo] = useState('');
  const [newJiraProject, setNewJiraProject] = useState('');
  const [newJiraComponent, setNewJiraComponent] = useState('');

  // Fetch fields
  const { data: fieldsData, isLoading } = useQuery({
    queryKey: ['fields'],
    queryFn: listFields,
  });

  // Field mutations
  const createFieldMutation = useMutation({
    mutationFn: createField,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fields'] });
      closeFieldModal();
    },
  });

  const updateFieldMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: FieldCreateRequest }) => updateField(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fields'] });
      closeFieldModal();
    },
  });

  const deleteFieldMutation = useMutation({
    mutationFn: deleteField,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fields'] });
    },
  });

  // Project mutations
  const createProjectMutation = useMutation({
    mutationFn: ({ fieldId, data }: { fieldId: number; data: ProjectCreateRequest }) =>
      createProject(fieldId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fields'] });
      closeProjectModal();
    },
  });

  const updateProjectMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProjectCreateRequest }) => updateProject(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fields'] });
      closeProjectModal();
    },
  });

  const deleteProjectMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fields'] });
    },
  });

  // Redetect mutation
  const redetectMutation = useMutation({
    mutationFn: redetectActivities,
    onSuccess: (result) => {
      setRedetectResult(result.message);
      setTimeout(() => setRedetectResult(null), 5000);
    },
  });

  // Modal handlers
  const openFieldModal = (field?: ReportField) => {
    if (field) {
      setEditingField(field);
      setFieldForm({ name: field.name, description: field.description || '' });
    } else {
      setEditingField(null);
      setFieldForm({ name: '', description: '' });
    }
    setIsFieldModalOpen(true);
  };

  const closeFieldModal = () => {
    setIsFieldModalOpen(false);
    setEditingField(null);
    setFieldForm({ name: '', description: '' });
  };

  const openProjectModal = (fieldId: number, project?: ReportProject, parentId?: number | null) => {
    setSelectedFieldId(fieldId);
    setSelectedParentId(parentId ?? null);
    if (project) {
      setEditingProject(project);
      setProjectForm({
        name: project.name,
        description: project.description || '',
        parent_id: project.parent_id,
        git_repos: project.git_repos || [],
        jira_components: project.jira_components || [],
      });
    } else {
      setEditingProject(null);
      setProjectForm({
        name: '',
        description: '',
        parent_id: parentId ?? null,
        git_repos: [],
        jira_components: [],
      });
    }
    setIsProjectModalOpen(true);
  };

  const closeProjectModal = () => {
    setIsProjectModalOpen(false);
    setEditingProject(null);
    setSelectedFieldId(null);
    setSelectedParentId(null);
    setProjectForm({ name: '', description: '', parent_id: null, git_repos: [], jira_components: [] });
    setNewGitRepo('');
    setNewJiraProject('');
    setNewJiraComponent('');
  };

  // Field handlers
  const handleSaveField = () => {
    if (!fieldForm.name) return;
    
    if (editingField) {
      updateFieldMutation.mutate({ id: editingField.id, data: fieldForm });
    } else {
      createFieldMutation.mutate(fieldForm);
    }
  };

  const handleDeleteField = (field: ReportField) => {
    if (confirm(`Delete field "${field.name}" and all its projects?`)) {
      deleteFieldMutation.mutate(field.id);
    }
  };

  // Project handlers
  const handleSaveProject = () => {
    if (!projectForm.name || !selectedFieldId) return;

    if (editingProject) {
      updateProjectMutation.mutate({ id: editingProject.id, data: projectForm });
    } else {
      createProjectMutation.mutate({ fieldId: selectedFieldId, data: projectForm });
    }
  };

  const handleDeleteProject = (project: ReportProject) => {
    const hasChildren = project.children && project.children.length > 0;
    const message = hasChildren
      ? `Delete project "${project.name}" and all its ${project.children.length} subproject(s)?`
      : `Delete project "${project.name}"?`;
    if (confirm(message)) {
      deleteProjectMutation.mutate(project.id);
    }
  };

  // Helper to count total projects in a field (including nested)
  const countTotalProjects = (projects: ReportProject[]): number => {
    return projects.reduce((sum, p) => sum + 1 + countTotalProjects(p.children || []), 0);
  };

  // Recursive component to render projects with their children
  const ProjectTree = ({ 
    project, 
    fieldId, 
    depth = 0 
  }: { 
    project: ReportProject; 
    fieldId: number; 
    depth?: number;
  }) => {
    const hasChildren = project.children && project.children.length > 0;
    const isLeaf = project.is_leaf;
    
    return (
      <ExpandableSection
        key={project.id}
        toggleContent={
          <span>
            {project.name}
            {hasChildren && (
              <Label color="blue" style={{ marginLeft: '0.5rem' }} isCompact>
                {project.children.length} subproject{project.children.length !== 1 ? 's' : ''}
              </Label>
            )}
            {isLeaf && (
              <Label color="green" style={{ marginLeft: '0.5rem' }} isCompact>
                leaf
              </Label>
            )}
          </span>
        }
        style={{ marginBottom: '0.5rem', marginLeft: depth > 0 ? '1.5rem' : 0 }}
      >
        <Card isPlain style={{ marginLeft: '1rem' }}>
          <CardBody>
            <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
              <FlexItem style={{ flex: 1 }}>
                {project.description && <p style={{ marginBottom: '0.5rem' }}>{project.description}</p>}
                
                {/* Only show detection mappings for leaf projects */}
                {isLeaf ? (
                  <>
                    <div style={{ marginBottom: '0.5rem' }}>
                      <strong><CodeBranchIcon style={{ marginRight: '0.25rem' }} /> Git Repos:</strong>{' '}
                      {project.git_repos.length > 0 ? (
                        <LabelGroup>
                          {project.git_repos.map((repo) => (
                            <Label key={repo}>{repo}</Label>
                          ))}
                        </LabelGroup>
                      ) : (
                        <em>None configured</em>
                      )}
                    </div>
                    
                    <div>
                      <strong>Jira Components:</strong>{' '}
                      {project.jira_components.length > 0 ? (
                        <LabelGroup>
                          {project.jira_components.map((comp, idx) => (
                            <Label key={idx}>
                              {comp.jira_project_key}/{comp.component_name}
                            </Label>
                          ))}
                        </LabelGroup>
                      ) : (
                        <em>None configured</em>
                      )}
                    </div>
                  </>
                ) : (
                  <p style={{ fontStyle: 'italic', color: '#6a6e73' }}>
                    Detection mappings are configured on subprojects (leaf nodes only)
                  </p>
                )}
              </FlexItem>
              <FlexItem>
                <Button
                  variant="secondary"
                  icon={<PlusIcon />}
                  onClick={() => openProjectModal(fieldId, undefined, project.id)}
                  style={{ marginRight: '0.25rem' }}
                  size="sm"
                >
                  Add Subproject
                </Button>
                <Button
                  variant="plain"
                  icon={<EditAltIcon />}
                  onClick={() => openProjectModal(fieldId, project)}
                  style={{ marginRight: '0.25rem' }}
                />
                <Button
                  variant="plain"
                  isDanger
                  icon={<TrashIcon />}
                  onClick={() => handleDeleteProject(project)}
                />
              </FlexItem>
            </Flex>
            
            {/* Render children recursively */}
            {hasChildren && (
              <div style={{ marginTop: '1rem' }}>
                {project.children.map((child) => (
                  <ProjectTree 
                    key={child.id} 
                    project={child} 
                    fieldId={fieldId} 
                    depth={depth + 1} 
                  />
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </ExpandableSection>
    );
  };

  // Git repo handlers
  const addGitRepo = () => {
    if (newGitRepo && !projectForm.git_repos?.includes(newGitRepo)) {
      setProjectForm({
        ...projectForm,
        git_repos: [...(projectForm.git_repos || []), newGitRepo],
      });
      setNewGitRepo('');
    }
  };

  const removeGitRepo = (repo: string) => {
    setProjectForm({
      ...projectForm,
      git_repos: projectForm.git_repos?.filter((r) => r !== repo) || [],
    });
  };

  // Jira component handlers
  const addJiraComponent = () => {
    if (newJiraProject && newJiraComponent) {
      const newComp: JiraComponentConfig = {
        jira_project_key: newJiraProject,
        component_name: newJiraComponent,
      };
      const existing = projectForm.jira_components || [];
      const isDupe = existing.some(
        (c) => c.jira_project_key === newJiraProject && c.component_name === newJiraComponent
      );
      if (!isDupe) {
        setProjectForm({
          ...projectForm,
          jira_components: [...existing, newComp],
        });
        setNewJiraProject('');
        setNewJiraComponent('');
      }
    }
  };

  const removeJiraComponent = (comp: JiraComponentConfig) => {
    setProjectForm({
      ...projectForm,
      jira_components:
        projectForm.jira_components?.filter(
          (c) => !(c.jira_project_key === comp.jira_project_key && c.component_name === comp.component_name)
        ) || [],
    });
  };

  return (
    <>
      <PageSection>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
          <FlexItem>
            <Content>
              <Title headingLevel="h1">Report Fields Configuration</Title>
              <p>Configure fields and projects for report consolidation. Activities are auto-assigned to projects based on git repos and Jira components.</p>
            </Content>
          </FlexItem>
          <FlexItem>
            <Flex>
              <FlexItem>
                <Button
                  variant="secondary"
                  icon={<SyncAltIcon />}
                  onClick={() => redetectMutation.mutate({ limit: 5000 })}
                  isLoading={redetectMutation.isPending}
                >
                  Redetect Activities
                </Button>
              </FlexItem>
              <FlexItem>
                <Button
                  variant="primary"
                  icon={<PlusIcon />}
                  onClick={() => openFieldModal()}
                >
                  Add Field
                </Button>
              </FlexItem>
            </Flex>
          </FlexItem>
        </Flex>
      </PageSection>

      {redetectResult && (
        <PageSection>
          <Alert variant="success" isInline title={redetectResult} />
        </PageSection>
      )}

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : fieldsData?.fields.length ? (
          fieldsData.fields.map((field) => (
            <Card key={field.id} style={{ marginBottom: '1rem' }}>
              <CardTitle>
                <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
                  <FlexItem>
                    <Flex alignItems={{ default: 'alignItemsCenter' }}>
                      <FlexItem>
                        <CubesIcon style={{ marginRight: '0.5rem' }} />
                        {field.name}
                      </FlexItem>
                      <FlexItem>
                        <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                          {countTotalProjects(field.projects)} project{countTotalProjects(field.projects) !== 1 ? 's' : ''}
                        </Label>
                      </FlexItem>
                    </Flex>
                  </FlexItem>
                  <FlexItem>
                    <Button
                      variant="secondary"
                      icon={<PlusIcon />}
                      onClick={() => openProjectModal(field.id, undefined, null)}
                      style={{ marginRight: '0.5rem' }}
                    >
                      Add Project
                    </Button>
                    <Button
                      variant="plain"
                      icon={<EditAltIcon />}
                      onClick={() => openFieldModal(field)}
                      style={{ marginRight: '0.5rem' }}
                    />
                    <Button
                      variant="plain"
                      isDanger
                      icon={<TrashIcon />}
                      onClick={() => handleDeleteField(field)}
                    />
                  </FlexItem>
                </Flex>
              </CardTitle>
              <CardBody>
                {field.description && <p style={{ marginBottom: '1rem' }}>{field.description}</p>}
                
                {field.projects.length > 0 ? (
                  field.projects.map((project) => (
                    <ProjectTree 
                      key={project.id} 
                      project={project} 
                      fieldId={field.id} 
                    />
                  ))
                ) : (
                  <p><em>No projects yet. Add one to start configuring detection rules.</em></p>
                )}
              </CardBody>
            </Card>
          ))
        ) : (
          <Card>
            <CardBody>
              <p>No fields configured yet. Click "Add Field" to create your first field.</p>
            </CardBody>
          </Card>
        )}
      </PageSection>

      {/* Field Modal */}
      <Modal
        isOpen={isFieldModalOpen}
        onClose={closeFieldModal}
        aria-labelledby="field-modal"
        variant="medium"
      >
        <ModalHeader title={editingField ? 'Edit Field' : 'Create Field'} labelId="field-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Field Name" isRequired fieldId="field-name">
              <TextInput
                isRequired
                id="field-name"
                value={fieldForm.name}
                onChange={(_event, value) => setFieldForm({ ...fieldForm, name: value })}
                placeholder="e.g., Platform, Infrastructure, Mobile"
              />
            </FormGroup>
            <FormGroup label="Description" fieldId="field-description">
              <TextArea
                id="field-description"
                value={fieldForm.description || ''}
                onChange={(_event, value) => setFieldForm({ ...fieldForm, description: value })}
                rows={2}
                placeholder="Optional description for this field"
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleSaveField}
            isLoading={createFieldMutation.isPending || updateFieldMutation.isPending}
            isDisabled={!fieldForm.name}
          >
            {editingField ? 'Save' : 'Create'}
          </Button>
          <Button variant="link" onClick={closeFieldModal}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>

      {/* Project Modal */}
      <Modal
        isOpen={isProjectModalOpen}
        onClose={closeProjectModal}
        aria-labelledby="project-modal"
        variant="large"
      >
        <ModalHeader 
          title={
            editingProject 
              ? 'Edit Project' 
              : selectedParentId 
                ? 'Create Subproject' 
                : 'Create Project'
          } 
          labelId="project-modal" 
        />
        <ModalBody>
          <Form>
            {selectedParentId && !editingProject && (
              <Alert 
                variant="info" 
                isInline 
                title="Creating subproject"
                style={{ marginBottom: '1rem' }}
              >
                This will be created as a subproject. Detection mappings can only be configured on leaf projects (projects without children).
              </Alert>
            )}
            
            <FormGroup label="Project Name" isRequired fieldId="project-name">
              <TextInput
                isRequired
                id="project-name"
                value={projectForm.name}
                onChange={(_event, value) => setProjectForm({ ...projectForm, name: value })}
                placeholder="e.g., API Development, SDK, CI/CD"
              />
            </FormGroup>
            
            <FormGroup label="Description" fieldId="project-description">
              <TextArea
                id="project-description"
                value={projectForm.description || ''}
                onChange={(_event, value) => setProjectForm({ ...projectForm, description: value })}
                rows={2}
                placeholder="Optional description"
              />
            </FormGroup>

            {/* Only show detection mappings for leaf projects (no children) */}
            {(!editingProject || editingProject.is_leaf) && (
              <>
                <FormGroup
                  label="Git Repositories"
                  fieldId="git-repos"
                >
                  <Flex>
                    <FlexItem style={{ flex: 1 }}>
                      <TextInput
                        id="new-git-repo"
                        value={newGitRepo}
                        onChange={(_event, value) => setNewGitRepo(value)}
                        placeholder="e.g., myorg/myrepo or myorg/*"
                        onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addGitRepo())}
                      />
                    </FlexItem>
                    <FlexItem>
                      <Button variant="secondary" onClick={addGitRepo} isDisabled={!newGitRepo}>
                        Add
                      </Button>
                    </FlexItem>
                  </Flex>
                  <FormHelperText>
                    <HelperText>
                      <HelperTextItem>Add git repo patterns for auto-detection. Use wildcards like 'org/*' to match multiple repos.</HelperTextItem>
                    </HelperText>
                  </FormHelperText>
                  {projectForm.git_repos && projectForm.git_repos.length > 0 && (
                    <LabelGroup style={{ marginTop: '0.5rem' }}>
                      {projectForm.git_repos.map((repo) => (
                        <Label key={repo} onClose={() => removeGitRepo(repo)}>
                          {repo}
                        </Label>
                      ))}
                    </LabelGroup>
                  )}
                </FormGroup>

                <FormGroup
                  label="Jira Components"
                  fieldId="jira-components"
                >
                  <Flex>
                    <FlexItem>
                      <TextInput
                        id="new-jira-project"
                        value={newJiraProject}
                        onChange={(_event, value) => setNewJiraProject(value)}
                        placeholder="Project key (e.g., APPENG)"
                        style={{ width: '150px' }}
                      />
                    </FlexItem>
                    <FlexItem style={{ flex: 1 }}>
                      <TextInput
                        id="new-jira-component"
                        value={newJiraComponent}
                        onChange={(_event, value) => setNewJiraComponent(value)}
                        placeholder="Component name (e.g., API)"
                        onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addJiraComponent())}
                      />
                    </FlexItem>
                    <FlexItem>
                      <Button
                        variant="secondary"
                        onClick={addJiraComponent}
                        isDisabled={!newJiraProject || !newJiraComponent}
                      >
                        Add
                      </Button>
                    </FlexItem>
                  </Flex>
                  <FormHelperText>
                    <HelperText>
                      <HelperTextItem>Add Jira project + component pairs for auto-detection.</HelperTextItem>
                    </HelperText>
                  </FormHelperText>
                  {projectForm.jira_components && projectForm.jira_components.length > 0 && (
                    <LabelGroup style={{ marginTop: '0.5rem' }}>
                      {projectForm.jira_components.map((comp, idx) => (
                        <Label key={idx} onClose={() => removeJiraComponent(comp)}>
                          {comp.jira_project_key}/{comp.component_name}
                        </Label>
                      ))}
                    </LabelGroup>
                  )}
                </FormGroup>
              </>
            )}
            
            {editingProject && !editingProject.is_leaf && (
              <Alert 
                variant="info" 
                isInline 
                title="Non-leaf project"
                style={{ marginTop: '1rem' }}
              >
                This project has subprojects, so detection mappings are configured on its children instead.
              </Alert>
            )}
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleSaveProject}
            isLoading={createProjectMutation.isPending || updateProjectMutation.isPending}
            isDisabled={!projectForm.name}
          >
            {editingProject ? 'Save' : 'Create'}
          </Button>
          <Button variant="link" onClick={closeProjectModal}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default FieldsConfigPage;

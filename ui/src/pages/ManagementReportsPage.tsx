/**
 * Management Reports page - create and view management reports (manager only)
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  CardBody,
  CardTitle,
  Content,
  Flex,
  FlexItem,
  Form,
  FormGroup,
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
} from '@patternfly/react-core';
import { PlusIcon } from '@patternfly/react-icons';
import { format } from 'date-fns';
import Markdown from 'react-markdown';
import {
  listManagementReports,
  createManagementReport,
  deleteManagementReport,
} from '@/api/reports';
import type { ManagementReportCreateRequest } from '@/types';

// Styles for rendered markdown
const markdownContainerStyle: React.CSSProperties = {
  padding: '1rem',
  background: 'var(--pf-v6-global--BackgroundColor--200)',
  borderRadius: '4px',
  marginTop: '1rem',
  maxHeight: '400px',
  overflow: 'auto',
};

export function ManagementReportsPage() {
  const queryClient = useQueryClient();

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newReport, setNewReport] = useState<ManagementReportCreateRequest>({
    title: '',
    content: '',
    project_key: '',
    report_period: '',
    referenced_tickets: [],
  });

  // Fetch management reports
  const { data: reportsData, isLoading } = useQuery({
    queryKey: ['managementReports'],
    queryFn: () => listManagementReports({ limit: 50 }),
  });

  // Create report mutation
  const createMutation = useMutation({
    mutationFn: createManagementReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managementReports'] });
      setIsModalOpen(false);
      setNewReport({
        title: '',
        content: '',
        project_key: '',
        report_period: '',
        referenced_tickets: [],
      });
    },
  });

  // Delete report mutation
  const deleteMutation = useMutation({
    mutationFn: deleteManagementReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['managementReports'] });
    },
  });

  const handleCreate = () => {
    if (newReport.title && newReport.content) {
      createMutation.mutate(newReport);
    }
  };

  const handleDelete = (reportId: number) => {
    if (confirm('Are you sure you want to delete this report?')) {
      deleteMutation.mutate(reportId);
    }
  };

  return (
    <>
      <PageSection>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
          <FlexItem>
            <Content>
              <Title headingLevel="h1">Management Reports</Title>
            </Content>
          </FlexItem>
          <FlexItem>
            <Button
              variant="primary"
              icon={<PlusIcon />}
              onClick={() => setIsModalOpen(true)}
            >
              Create Report
            </Button>
          </FlexItem>
        </Flex>
      </PageSection>

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : reportsData?.reports.length ? (
          reportsData.reports.map((report) => (
            <Card key={report.id} style={{ marginBottom: '1rem' }}>
              <CardTitle>
                <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
                  <FlexItem>
                    {report.title}
                    {report.project_key && (
                      <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                        {report.project_key}
                      </Label>
                    )}
                    {report.report_period && (
                      <Label color="grey" style={{ marginLeft: '0.5rem' }}>
                        {report.report_period}
                      </Label>
                    )}
                  </FlexItem>
                  <FlexItem>
                    <small>
                      {report.created_at && format(new Date(report.created_at), 'MMM d, yyyy')}
                    </small>
                    <Button
                      variant="link"
                      isDanger
                      onClick={() => handleDelete(report.id)}
                      style={{ marginLeft: '1rem' }}
                    >
                      Delete
                    </Button>
                  </FlexItem>
                </Flex>
              </CardTitle>
              <CardBody>
                <div style={markdownContainerStyle}>
                  <Markdown>{report.content}</Markdown>
                </div>
                
                {report.referenced_tickets.length > 0 && (
                  <p style={{ marginTop: '1rem' }}>
                    <strong>Referenced Tickets:</strong>{' '}
                    {report.referenced_tickets.join(', ')}
                  </p>
                )}
              </CardBody>
            </Card>
          ))
        ) : (
          <Card>
            <CardBody>
              <p>No management reports yet. Click "Create Report" to add one.</p>
            </CardBody>
          </Card>
        )}
      </PageSection>

      {/* Create Report Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        aria-labelledby="create-report-modal"
        variant="large"
      >
        <ModalHeader title="Create Management Report" labelId="create-report-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Title" isRequired fieldId="title">
              <TextInput
                isRequired
                id="title"
                value={newReport.title}
                onChange={(_event, value) => setNewReport({ ...newReport, title: value })}
                placeholder="e.g., Week 4, January 2026"
              />
            </FormGroup>

            <FormGroup label="Project Key" fieldId="project-key">
              <TextInput
                id="project-key"
                value={newReport.project_key || ''}
                onChange={(_event, value) => setNewReport({ ...newReport, project_key: value })}
                placeholder="e.g., APPENG"
              />
            </FormGroup>

            <FormGroup label="Report Period" fieldId="report-period">
              <TextInput
                id="report-period"
                value={newReport.report_period || ''}
                onChange={(_event, value) => setNewReport({ ...newReport, report_period: value })}
                placeholder="e.g., Week 3, Jan 2026"
              />
            </FormGroup>

            <FormGroup label="Report Content (Markdown)" isRequired fieldId="content">
              <TextArea
                isRequired
                id="content"
                value={newReport.content}
                onChange={(_event, value) => setNewReport({ ...newReport, content: value })}
                placeholder="Bullet list of work items with embedded links"
                rows={12}
              />
            </FormGroup>

            <FormGroup label="Referenced Tickets (comma-separated)" fieldId="tickets">
              <TextInput
                id="tickets"
                value={newReport.referenced_tickets?.join(', ') || ''}
                onChange={(_event, value) =>
                  setNewReport({
                    ...newReport,
                    referenced_tickets: value.split(',').map((t) => t.trim()).filter(Boolean),
                  })
                }
                placeholder="e.g., PROJ-123, owner/repo#456"
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleCreate}
            isLoading={createMutation.isPending}
            isDisabled={!newReport.title || !newReport.content}
          >
            Create Report
          </Button>
          <Button variant="link" onClick={() => setIsModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default ManagementReportsPage;

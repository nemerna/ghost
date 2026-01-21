/**
 * Management Reports page - create and view management reports (manager only)
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardTitle,
  ExpandableSection,
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
  PageSectionVariants,
  Spinner,
  Text,
  TextArea,
  TextContent,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { PlusIcon } from '@patternfly/react-icons';
import { format } from 'date-fns';
import {
  listManagementReports,
  createManagementReport,
  deleteManagementReport,
} from '@/api/reports';
import type { ManagementReportCreateRequest } from '@/types';

export function ManagementReportsPage() {
  const queryClient = useQueryClient();

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newReport, setNewReport] = useState<ManagementReportCreateRequest>({
    title: '',
    executive_summary: '',
    content: '',
    one_liner: '',
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
        executive_summary: '',
        content: '',
        one_liner: '',
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
    if (newReport.title && newReport.executive_summary && newReport.content) {
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
      <PageSection variant={PageSectionVariants.light}>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
          <FlexItem>
            <TextContent>
              <Title headingLevel="h1">Management Reports</Title>
            </TextContent>
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
                    <Text component="small">
                      {report.created_at && format(new Date(report.created_at), 'MMM d, yyyy')}
                    </Text>
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
                {report.one_liner && (
                  <Alert variant="info" isInline title={report.one_liner} style={{ marginBottom: '1rem' }} />
                )}
                
                <p><strong>Executive Summary:</strong></p>
                <p style={{ marginBottom: '1rem' }}>{report.executive_summary}</p>
                
                {report.referenced_tickets.length > 0 && (
                  <p>
                    <strong>Referenced Tickets:</strong>{' '}
                    {report.referenced_tickets.join(', ')}
                  </p>
                )}

                <ExpandableSection toggleText="View full report">
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    background: 'var(--pf-v6-global--BackgroundColor--200)',
                    padding: '1rem',
                    borderRadius: '4px',
                    marginTop: '1rem'
                  }}>
                    {report.content}
                  </pre>
                </ExpandableSection>
              </CardBody>
            </Card>
          ))
        ) : (
          <Card>
            <CardBody>
              <Text>No management reports yet. Click "Create Report" to add one.</Text>
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
                placeholder="e.g., APPENG Progress - Week 3"
              />
            </FormGroup>

            <FormGroup label="One-liner (max 15 words)" fieldId="one-liner">
              <TextInput
                id="one-liner"
                value={newReport.one_liner || ''}
                onChange={(_event, value) => setNewReport({ ...newReport, one_liner: value })}
                placeholder="Brief elevator pitch"
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

            <FormGroup label="Executive Summary" isRequired fieldId="executive-summary">
              <TextArea
                isRequired
                id="executive-summary"
                value={newReport.executive_summary}
                onChange={(_event, value) => setNewReport({ ...newReport, executive_summary: value })}
                placeholder="2-3 sentences summarizing the key outcomes"
                rows={3}
              />
            </FormGroup>

            <FormGroup label="Full Report Content (Markdown)" isRequired fieldId="content">
              <TextArea
                isRequired
                id="content"
                value={newReport.content}
                onChange={(_event, value) => setNewReport({ ...newReport, content: value })}
                placeholder="Full report content in Markdown format"
                rows={10}
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
                placeholder="e.g., PROJ-123, PROJ-456"
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleCreate}
            isLoading={createMutation.isPending}
            isDisabled={!newReport.title || !newReport.executive_summary || !newReport.content}
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

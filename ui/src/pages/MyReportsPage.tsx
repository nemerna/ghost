/**
 * My Reports page - view and create weekly reports
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
import { LockIcon, EyeIcon } from '@patternfly/react-icons';
import {
  generateWeeklyReport,
  getMyWeeklyReports,
  saveWeeklyReport,
  deleteWeeklyReport,
  updateWeeklyReportVisibility,
} from '@/api/reports';
import { StyledMarkdown, InlineMarkdown } from '@/components/StyledMarkdown';
import type { GeneratedReport, WeeklyReport } from '@/types';

export function MyReportsPage() {
  const queryClient = useQueryClient();

  // Modal state
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [weekOffset, setWeekOffset] = useState(0);
  const [generatedReport, setGeneratedReport] = useState<GeneratedReport | null>(null);
  const [customTitle, setCustomTitle] = useState('');
  const [customSummary, setCustomSummary] = useState('');

  // Fetch saved reports
  const { data: savedReports, isLoading } = useQuery({
    queryKey: ['myWeeklyReports'],
    queryFn: () => getMyWeeklyReports({ limit: 20 }),
  });

  // Generate report mutation
  const generateMutation = useMutation({
    mutationFn: (offset: number) => generateWeeklyReport(offset),
    onSuccess: (data) => {
      setGeneratedReport(data);
      setCustomTitle(data.title);
      setCustomSummary(data.summary);
    },
  });

  // Save report mutation
  const saveMutation = useMutation({
    mutationFn: () =>
      saveWeeklyReport({
        week_offset: weekOffset,
        custom_title: customTitle || undefined,
        custom_summary: customSummary || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myWeeklyReports'] });
      setIsGenerateModalOpen(false);
      setGeneratedReport(null);
      setCustomTitle('');
      setCustomSummary('');
    },
  });

  // Delete report mutation
  const deleteMutation = useMutation({
    mutationFn: deleteWeeklyReport,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myWeeklyReports'] });
    },
  });

  // Update visibility mutation
  const visibilityMutation = useMutation({
    mutationFn: ({ id, visible }: { id: number; visible: boolean | null }) =>
      updateWeeklyReportVisibility(id, visible),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myWeeklyReports'] });
    },
  });

  const handleToggleVisibility = (report: WeeklyReport) => {
    // Cycle through: null (inherit) -> true (visible) -> false (hidden) -> null
    let newValue: boolean | null;
    if (report.visible_to_manager === null) {
      newValue = true;
    } else if (report.visible_to_manager === true) {
      newValue = false;
    } else {
      newValue = null;
    }
    visibilityMutation.mutate({ id: report.id, visible: newValue });
  };

  const getVisibilityInfo = (report: WeeklyReport) => {
    if (report.visible_to_manager === true) {
      return { icon: <EyeIcon />, tooltip: 'Visible to manager (override)', color: 'green' };
    } else if (report.visible_to_manager === false) {
      return { icon: <LockIcon />, tooltip: 'Hidden from manager (override)', color: 'red' };
    } else {
      return { icon: <EyeIcon />, tooltip: 'Using default visibility', color: 'grey' };
    }
  };

  const handleOpenGenerateModal = () => {
    setIsGenerateModalOpen(true);
    setWeekOffset(0);
    setGeneratedReport(null);
  };

  const handleGenerate = () => {
    generateMutation.mutate(weekOffset);
  };

  const handleSave = () => {
    saveMutation.mutate();
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
              <Title headingLevel="h1">My Weekly Reports</Title>
            </Content>
          </FlexItem>
          <FlexItem>
            <Button variant="primary" onClick={handleOpenGenerateModal}>
              Generate Report
            </Button>
          </FlexItem>
        </Flex>
      </PageSection>

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : savedReports?.reports.length ? (
          <>
            {savedReports.reports.map((report) => {
              const visInfo = getVisibilityInfo(report);
              return (
              <Card key={report.id} style={{ marginBottom: '1rem' }}>
                <CardTitle>
                  <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
                    <FlexItem>
                      {report.title}
                      <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                        {report.tickets_count} tickets
                      </Label>
                    </FlexItem>
                    <FlexItem>
                      <Button
                        variant="plain"
                        aria-label={visInfo.tooltip}
                        title={visInfo.tooltip}
                        onClick={() => handleToggleVisibility(report)}
                        isLoading={visibilityMutation.isPending}
                        style={{ color: visInfo.color }}
                      >
                        {visInfo.icon}
                      </Button>
                      <Button
                        variant="link"
                        isDanger
                        onClick={() => handleDelete(report.id)}
                      >
                        Delete
                      </Button>
                    </FlexItem>
                  </Flex>
                </CardTitle>
                <CardBody>
                  <p><strong>Period:</strong> {report.week_start} to {report.week_end}</p>
                  <p><strong>Summary:</strong> <InlineMarkdown>{report.summary}</InlineMarkdown></p>
                  <p><strong>Projects:</strong> {report.projects.join(', ') || 'None'}</p>
                  
                  <ExpandableSection toggleText="View full report">
                    <StyledMarkdown maxHeight="400px">{report.content}</StyledMarkdown>
                  </ExpandableSection>
                </CardBody>
              </Card>
            );
            })}
          </>
        ) : (
          <Card>
            <CardBody>
              <Content>
                <p>No reports yet. Click "Generate Report" to create your first weekly report.</p>
              </Content>
            </CardBody>
          </Card>
        )}
      </PageSection>

      {/* Generate Report Modal */}
      <Modal
        isOpen={isGenerateModalOpen}
        onClose={() => setIsGenerateModalOpen(false)}
        aria-labelledby="generate-report-modal"
        variant="large"
      >
        <ModalHeader title="Generate Weekly Report" labelId="generate-report-modal" />
        <ModalBody>
          <Form>
            <FormGroup label="Week" fieldId="week-offset">
              <Flex>
                <FlexItem>
                  <Button
                    variant={weekOffset === 0 ? 'primary' : 'secondary'}
                    onClick={() => setWeekOffset(0)}
                  >
                    This Week
                  </Button>
                </FlexItem>
                <FlexItem>
                  <Button
                    variant={weekOffset === -1 ? 'primary' : 'secondary'}
                    onClick={() => setWeekOffset(-1)}
                  >
                    Last Week
                  </Button>
                </FlexItem>
                <FlexItem>
                  <Button
                    variant="secondary"
                    onClick={handleGenerate}
                    isLoading={generateMutation.isPending}
                  >
                    Generate Preview
                  </Button>
                </FlexItem>
              </Flex>
            </FormGroup>

            {generatedReport && (
              <>
                <Alert
                  variant="info"
                  title={`Report for ${generatedReport.week_start} to ${generatedReport.week_end}`}
                  style={{ marginBottom: '1rem' }}
                >
                  {generatedReport.tickets_count} tickets, {Object.values(generatedReport.statistics).reduce((a, b) => a + b, 0)} actions
                </Alert>

                <FormGroup label="Title" fieldId="custom-title">
                  <TextInput
                    id="custom-title"
                    value={customTitle}
                    onChange={(_event, value) => setCustomTitle(value)}
                  />
                </FormGroup>

                <FormGroup label="Summary" fieldId="custom-summary">
                  <TextArea
                    id="custom-summary"
                    value={customSummary}
                    onChange={(_event, value) => setCustomSummary(value)}
                    rows={3}
                  />
                </FormGroup>

                <FormGroup label="Preview" fieldId="preview">
                  <StyledMarkdown maxHeight="300px">{generatedReport.content}</StyledMarkdown>
                </FormGroup>
              </>
            )}
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="primary"
            onClick={handleSave}
            isLoading={saveMutation.isPending}
            isDisabled={!generatedReport}
          >
            Save Report
          </Button>
          <Button variant="link" onClick={() => setIsGenerateModalOpen(false)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default MyReportsPage;

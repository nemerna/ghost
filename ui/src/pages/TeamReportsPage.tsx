/**
 * Team Reports page - view team members' weekly reports (manager only)
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  CardBody,
  CardTitle,
  ExpandableSection,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
  Label,
  PageSection,
  PageSectionVariants,
  Spinner,
  Text,
  TextContent,
  Title,
} from '@patternfly/react-core';
import { listTeams } from '@/api/teams';
import { getTeamWeeklyReports } from '@/api/reports';

export function TeamReportsPage() {
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);

  // Fetch teams
  const { data: teamsData, isLoading: teamsLoading } = useQuery({
    queryKey: ['teams'],
    queryFn: () => listTeams({ all_teams: true }),
  });

  // Fetch team weekly reports
  const { data: reportsData, isLoading: reportsLoading } = useQuery({
    queryKey: ['teamWeeklyReports', selectedTeamId],
    queryFn: () => getTeamWeeklyReports(selectedTeamId!, { limit: 50 }),
    enabled: !!selectedTeamId,
  });

  const isLoading = teamsLoading || (selectedTeamId && reportsLoading);

  // Auto-select first team
  React.useEffect(() => {
    if (teamsData?.teams.length && !selectedTeamId) {
      setSelectedTeamId(teamsData.teams[0].id);
    }
  }, [teamsData, selectedTeamId]);

  // Group reports by week
  const reportsByWeek = React.useMemo(() => {
    if (!reportsData?.reports) return {};
    
    const grouped: Record<string, typeof reportsData.reports> = {};
    reportsData.reports.forEach((report) => {
      const weekKey = `${report.week_start} - ${report.week_end}`;
      if (!grouped[weekKey]) {
        grouped[weekKey] = [];
      }
      grouped[weekKey].push(report);
    });
    return grouped;
  }, [reportsData]);

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
          <FlexItem>
            <TextContent>
              <Title headingLevel="h1">Team Weekly Reports</Title>
            </TextContent>
          </FlexItem>
          <FlexItem>
            <FormSelect
              value={selectedTeamId || ''}
              onChange={(_event, value) => setSelectedTeamId(Number(value))}
              aria-label="Select team"
              style={{ minWidth: '200px' }}
            >
              <FormSelectOption value="" label="Select a team" isDisabled />
              {teamsData?.teams.map((team) => (
                <FormSelectOption key={team.id} value={team.id} label={team.name} />
              ))}
            </FormSelect>
          </FlexItem>
        </Flex>
      </PageSection>

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <Spinner size="xl" />
          </Flex>
        ) : !selectedTeamId ? (
          <Card>
            <CardBody>
              <Text>Please select a team to view reports.</Text>
            </CardBody>
          </Card>
        ) : Object.keys(reportsByWeek).length === 0 ? (
          <Card>
            <CardBody>
              <Text>No reports found for this team.</Text>
            </CardBody>
          </Card>
        ) : (
          Object.entries(reportsByWeek).map(([weekKey, reports]) => (
            <Card key={weekKey} style={{ marginBottom: '1rem' }}>
              <CardTitle>
                Week: {weekKey}
                <Label color="blue" style={{ marginLeft: '0.5rem' }}>
                  {reports.length} reports
                </Label>
              </CardTitle>
              <CardBody>
                {reports.map((report) => (
                  <ExpandableSection
                    key={report.id}
                    toggleText={`${report.username} - ${report.tickets_count} tickets`}
                    style={{ marginBottom: '0.5rem' }}
                  >
                    <Card isPlain>
                      <CardBody>
                        <p><strong>Title:</strong> {report.title}</p>
                        <p><strong>Summary:</strong> {report.summary}</p>
                        <p><strong>Projects:</strong> {report.projects.join(', ') || 'None'}</p>
                        <pre style={{ 
                          whiteSpace: 'pre-wrap', 
                          background: 'var(--pf-v6-global--BackgroundColor--200)',
                          padding: '1rem',
                          borderRadius: '4px',
                          marginTop: '1rem',
                          maxHeight: '300px',
                          overflow: 'auto'
                        }}>
                          {report.content}
                        </pre>
                      </CardBody>
                    </Card>
                  </ExpandableSection>
                ))}
              </CardBody>
            </Card>
          ))
        )}
      </PageSection>
    </>
  );
}

export default TeamReportsPage;

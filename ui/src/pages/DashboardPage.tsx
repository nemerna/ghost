/**
 * Dashboard page - shows activity summary and quick stats
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  CardBody,
  CardTitle,
  Content,
  Divider,
  Flex,
  FlexItem,
  Grid,
  GridItem,
  Label,
  PageSection,
  Spinner,
  Title,
} from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr } from '@patternfly/react-table';
import {
  ClipboardCheckIcon,
  ExternalLinkAltIcon,
  GithubIcon,
  ListIcon,
} from '@patternfly/react-icons';
import { useAuth } from '@/auth';
import { getMyActivitySummary, getMyActivities } from '@/api/activities';
import { getTicketUrl } from '@/utils/tickets';
import { format } from 'date-fns';

// Ordered color palette for project bars — semantic nonstatus tokens (dark-mode safe)
const PROJECT_COLORS = [
  'var(--pf-t--global--color--nonstatus--blue--default)',
  'var(--pf-t--global--color--nonstatus--green--default)',
  'var(--pf-t--global--color--nonstatus--orange--default)',
  'var(--pf-t--global--color--nonstatus--red--default)',
  'var(--pf-t--global--color--nonstatus--purple--default)',
];

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const jiraServerUrl = (user?.preferences?.jira_server_url as string) || '';

  const { data: activitySummary, isLoading: summaryLoading } = useQuery({
    queryKey: ['activitySummary', 7],
    queryFn: () => getMyActivitySummary({ days: 7 }),
  });

  const { data: recentActivities, isLoading: activitiesLoading } = useQuery({
    queryKey: ['recentActivities'],
    queryFn: () => getMyActivities({ limit: 5 }),
  });

  const isLoading = summaryLoading || activitiesLoading;

  const heroStat = { title: 'Activities This Week', value: activitySummary?.total_activities || 0 };
  const secondaryStats = [
    { title: 'Tickets', value: activitySummary?.unique_tickets || 0, icon: <ListIcon color="var(--pf-t--global--color--nonstatus--purple--default)" /> },
    { title: 'Jira', value: activitySummary?.by_source?.jira || 0, icon: <ClipboardCheckIcon color="var(--pf-t--global--color--nonstatus--blue--default)" /> },
    { title: 'GitHub', value: activitySummary?.by_source?.github || 0, icon: <GithubIcon color="var(--pf-t--global--color--nonstatus--teal--default)" /> },
  ];

  const topProjects = Object.entries(activitySummary?.by_project ?? {})
    .sort(([, a], [, b]) => (b as number) - (a as number))
    .slice(0, 5);
  const maxProjectCount = (topProjects[0]?.[1] as number) || 1;

  return (
    <>
      <PageSection>
        <Content>
          <Title headingLevel="h1">Dashboard</Title>
          <p>Welcome back, {user?.display_name || user?.email}!</p>
        </Content>
      </PageSection>

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <FlexItem><Spinner size="xl" /></FlexItem>
          </Flex>
        ) : (
          <>
            <Grid hasGutter>
              {/* Left — Recent Activities (50%) */}
              <GridItem span={6}>
                <Card style={{ height: '100%' }}>
                  <CardTitle>
                    <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
                      <FlexItem>Recent Activities</FlexItem>
                      <FlexItem>
                        <Button variant="link" isInline onClick={() => navigate('/activities')} style={{ fontWeight: 'var(--pf-t--global--font--weight--body--default)', fontSize: 'var(--pf-t--global--font--size--body--sm)' }}>
                          View all
                        </Button>
                      </FlexItem>
                    </Flex>
                  </CardTitle>
                  <CardBody style={{ padding: 0 }}>
                    {recentActivities?.activities.length ? (
                      <Table aria-label="Recent activities" variant="compact">
                        <Thead>
                          <Tr>
                            <Th>Source</Th>
                            <Th>Ticket</Th>
                            <Th>Summary</Th>
                            <Th>Date</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {recentActivities.activities.map((activity) => {
                            const url = getTicketUrl(activity, jiraServerUrl);
                            return (
                              <Tr key={activity.id}>
                                <Td dataLabel="Source">
                                  <Label color={activity.ticket_source === 'github' ? 'purple' : 'blue'} isCompact>
                                    {activity.ticket_source === 'github' ? 'GitHub' : 'Jira'}
                                  </Label>
                                </Td>
                                <Td dataLabel="Ticket" modifier="nowrap">
                                  {url ? (
                                    <a href={url} target="_blank" rel="noopener noreferrer"
                                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                      {activity.ticket_key}
                                      <ExternalLinkAltIcon style={{ fontSize: '0.75em' }} />
                                    </a>
                                  ) : activity.ticket_key}
                                </Td>
                                <Td dataLabel="Summary" modifier="truncate">
                                  {activity.ticket_summary || '-'}
                                </Td>
                                <Td dataLabel="Date" modifier="nowrap">
                                  {format(new Date(activity.timestamp), 'MMM d, h:mm a')}
                                </Td>
                              </Tr>
                            );
                          })}
                        </Tbody>
                      </Table>
                    ) : (
                      <p style={{ padding: '1rem' }}>No recent activities</p>
                    )}
                  </CardBody>
                </Card>
              </GridItem>

              {/* Middle — one card, hero + divider + secondary stats */}
              <GridItem span={3}>
                <Card style={{ height: '100%' }}>
                  <CardTitle style={{ textAlign: 'center' }}>{heroStat.title}</CardTitle>
                  <CardBody>
                    <Flex direction={{ default: 'column' }} alignItems={{ default: 'alignItemsCenter' }}>
                      <FlexItem>
                        <Title headingLevel="h2" size="4xl">{heroStat.value}</Title>
                      </FlexItem>
                    </Flex>

                    <Divider style={{ margin: '2rem 0 1rem' }} />

                    <Grid hasGutter>
                      {secondaryStats.map((stat) => (
                        <GridItem key={stat.title} span={4}>
                          <Flex direction={{ default: 'column' }} alignItems={{ default: 'alignItemsCenter' }}>
                            <FlexItem>
                              <Content>{stat.icon} {stat.title}</Content>
                            </FlexItem>
                            <FlexItem>
                              <Title headingLevel="h3">{stat.value}</Title>
                            </FlexItem>
                          </Flex>
                        </GridItem>
                      ))}
                    </Grid>
                  </CardBody>
                </Card>
              </GridItem>

              {/* Right — Activity by Project (25%) */}
              <GridItem span={3}>
                {topProjects.length > 0 && (
                  <Card style={{ height: '100%' }}>
                    <CardTitle>Activity by Project</CardTitle>
                    <CardBody>
                      {topProjects.map(([project, count], i) => {
                        const color = PROJECT_COLORS[i % PROJECT_COLORS.length];
                        const barWidth = `${((count as number) / maxProjectCount) * 100}%`;
                        const isLast = i === topProjects.length - 1;
                        return (
                          <div
                            key={project}
                            style={{
                              paddingBottom: isLast ? 0 : '1rem',
                              marginBottom: isLast ? 0 : '1rem',
                              borderBottom: isLast ? 'none' : '1px solid var(--pf-t--global--border--color--default)',
                            }}
                          >
                            <Flex alignItems={{ default: 'alignItemsCenter' }} style={{ marginBottom: '0.4rem' }}>
                              <FlexItem>
                                <div style={{ width: '4px', height: '1.25rem', borderRadius: '2px', background: color }} />
                              </FlexItem>
                              <FlexItem flex={{ default: 'flex_1' }}>
                                {project}
                              </FlexItem>
                              <FlexItem>
                                {count as number} {(count as number) === 1 ? 'activity' : 'activities'}
                              </FlexItem>
                            </Flex>
                            <div style={{
                              height: '6px',
                              background: 'transparent',
                              borderRadius: '3px',
                              marginLeft: '12px',
                            }}>
                              <div style={{
                                height: '100%',
                                width: barWidth,
                                background: color,
                                borderRadius: '3px',
                                transition: 'width 0.3s ease',
                              }} />
                            </div>
                          </div>
                        );
                      })}
                    </CardBody>
                  </Card>
                )}
              </GridItem>
            </Grid>
          </>
        )}
      </PageSection>
    </>
  );
}

export default DashboardPage;

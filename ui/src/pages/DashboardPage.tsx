/**
 * Dashboard page - shows activity summary and quick stats
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  CardBody,
  Content,
  Flex,
  FlexItem,
  Grid,
  GridItem,
  Icon,
  Label,
  PageSection,
  Spinner,
  Title,
} from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr } from '@patternfly/react-table';
import {
  BundleIcon,
  ClipboardCheckIcon,
  ExternalLinkAltIcon,
  GithubIcon,
  ListIcon,
} from '@patternfly/react-icons';
import t_global_text_color_subtle from '@patternfly/react-tokens/dist/esm/t_global_text_color_subtle';
import { useAuth } from '@/auth';
import { getMyActivitySummary, getMyActivities } from '@/api/activities';
import { getTicketUrl } from '@/utils/tickets';
import { NONSTATUS_COLORS } from '@/utils/colors';
import { format } from 'date-fns';

const STAT_CARDS = [
  { key: 'activities', title: 'Activities', subtitle: 'This week', icon: BundleIcon },
  { key: 'tickets', title: 'Tickets', subtitle: 'Unique', icon: ListIcon },
  { key: 'jira', title: 'Jira', subtitle: 'Activities', icon: ClipboardCheckIcon },
  { key: 'github', title: 'GitHub', subtitle: 'Activities', icon: GithubIcon },
] as const;

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

  const statValues: Record<string, number> = {
    activities: activitySummary?.total_activities || 0,
    tickets: activitySummary?.unique_tickets || 0,
    jira: activitySummary?.by_source?.jira || 0,
    github: activitySummary?.by_source?.github || 0,
  };

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
          <Grid hasGutter>
            {/* Top row — 4 stat cards */}
            {STAT_CARDS.map(({ key, title, subtitle, icon: StatIcon }) => (
              <GridItem key={key} span={3}>
                <Card isCompact>
                  <CardBody>
                    <Flex spaceItems={{ default: 'spaceItemsMd' }} alignItems={{ default: 'alignItemsCenter' }}>
                      <FlexItem>
                        <Icon size="xl">
                          <StatIcon />
                        </Icon>
                      </FlexItem>
                      <Flex direction={{ default: 'column' }} spaceItems={{ default: 'spaceItemsNone' }}>
                        <FlexItem>
                          <Title headingLevel="h3" size="2xl" className="pf-v6-m-tabular-nums">
                            {statValues[key]}
                          </Title>
                        </FlexItem>
                        <FlexItem>
                          <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                            {title} &middot; {subtitle}
                          </Content>
                        </FlexItem>
                      </Flex>
                    </Flex>
                  </CardBody>
                </Card>
              </GridItem>
            ))}

            {/* Bottom left — Recent Activities (8 cols) */}
            <GridItem span={8}>
              <Card>
                <CardBody>
                  <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }} style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}>
                    <FlexItem>
                      <Title headingLevel="h2" size="lg">Recent Activities</Title>
                    </FlexItem>
                    <FlexItem>
                      <Button variant="link" isInline onClick={() => navigate('/activities')}>
                        View all
                      </Button>
                    </FlexItem>
                  </Flex>
                  {recentActivities?.activities.length ? (
                    <Table aria-label="Recent activities" variant="compact">
                      <Thead>
                        <Tr>
                          <Th width={10}>Source</Th>
                          <Th width={25}>Ticket</Th>
                          <Th width={45}>Summary</Th>
                          <Th width={20}>Date</Th>
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
                    <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                      No recent activities
                    </Content>
                  )}
                </CardBody>
              </Card>
            </GridItem>

            {/* Bottom right — Activity by Project (4 cols) */}
            <GridItem span={4}>
              <Card style={{ height: '100%' }}>
                <CardBody>
                  <Title headingLevel="h2" size="lg" style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}>
                    Activity by Project
                  </Title>
                  {topProjects.length > 0 ? (
                    topProjects.map(([project, count], i) => {
                      const color = NONSTATUS_COLORS[i % NONSTATUS_COLORS.length];
                      const barWidth = `${((count as number) / maxProjectCount) * 100}%`;
                      const isLast = i === topProjects.length - 1;
                      return (
                        <div
                          key={project}
                          style={{
                            paddingBottom: isLast ? 0 : 'var(--pf-t--global--spacer--md)',
                            marginBottom: isLast ? 0 : 'var(--pf-t--global--spacer--md)',
                            borderBottom: isLast ? 'none' : '1px solid var(--pf-t--global--border--color--default)',
                          }}
                        >
                          <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
                            <FlexItem>
                              <div style={{ width: '4px', height: '1.25rem', borderRadius: '2px', background: color }} />
                            </FlexItem>
                            <FlexItem flex={{ default: 'flex_1' }}>
                              {project}
                            </FlexItem>
                            <FlexItem>
                              <span style={{ color: t_global_text_color_subtle.var }}>
                                {count as number}
                              </span>
                            </FlexItem>
                          </Flex>
                          <div style={{ height: '6px', borderRadius: '3px', marginLeft: '12px' }}>
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
                    })
                  ) : (
                    <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                      No project data
                    </Content>
                  )}
                </CardBody>
              </Card>
            </GridItem>
          </Grid>
        )}
      </PageSection>
    </>
  );
}

export default DashboardPage;

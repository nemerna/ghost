/**
 * Dashboard page - shows activity summary and quick stats
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  CardBody,
  CardTitle,
  DescriptionList,
  DescriptionListDescription,
  DescriptionListGroup,
  DescriptionListTerm,
  Flex,
  FlexItem,
  Gallery,
  GalleryItem,
  PageSection,
  PageSectionVariants,
  Spinner,
  Text,
  TextContent,
  Title,
} from '@patternfly/react-core';
import {
  CheckCircleIcon,
  ClipboardCheckIcon,
  CodeIcon,
  CommentIcon,
} from '@patternfly/react-icons';
import { useAuth } from '@/auth';
import { getMyActivitySummary, getMyActivities } from '@/api/activities';
import { getMyWeeklyReports } from '@/api/reports';
import { format } from 'date-fns';

export function DashboardPage() {
  const { user } = useAuth();

  // Fetch activity summary for last 7 days
  const { data: activitySummary, isLoading: summaryLoading } = useQuery({
    queryKey: ['activitySummary', 7],
    queryFn: () => getMyActivitySummary(7),
  });

  // Fetch recent activities
  const { data: recentActivities, isLoading: activitiesLoading } = useQuery({
    queryKey: ['recentActivities'],
    queryFn: () => getMyActivities({ limit: 5 }),
  });

  // Fetch recent reports
  const { data: recentReports, isLoading: reportsLoading } = useQuery({
    queryKey: ['recentReports'],
    queryFn: () => getMyWeeklyReports({ limit: 3 }),
  });

  const isLoading = summaryLoading || activitiesLoading || reportsLoading;

  const statCards = [
    {
      title: 'Activities This Week',
      value: activitySummary?.total_activities || 0,
      icon: <ClipboardCheckIcon />,
    },
    {
      title: 'Unique Tickets',
      value: activitySummary?.unique_tickets || 0,
      icon: <CodeIcon />,
    },
    {
      title: 'Comments Added',
      value: activitySummary?.by_action_type?.comment || 0,
      icon: <CommentIcon />,
    },
    {
      title: 'Tickets Created',
      value: activitySummary?.by_action_type?.create || 0,
      icon: <CheckCircleIcon />,
    },
  ];

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <TextContent>
          <Title headingLevel="h1">Dashboard</Title>
          <Text component="p">
            Welcome back, {user?.display_name || user?.email}!
          </Text>
        </TextContent>
      </PageSection>

      <PageSection>
        {isLoading ? (
          <Flex justifyContent={{ default: 'justifyContentCenter' }}>
            <FlexItem>
              <Spinner size="xl" />
            </FlexItem>
          </Flex>
        ) : (
          <>
            {/* Stats Cards */}
            <Gallery hasGutter minWidths={{ default: '250px' }}>
              {statCards.map((stat, index) => (
                <GalleryItem key={index}>
                  <Card isCompact>
                    <CardTitle>
                      <Flex>
                        <FlexItem>{stat.icon}</FlexItem>
                        <FlexItem>
                          <Text component="small">{stat.title}</Text>
                        </FlexItem>
                      </Flex>
                    </CardTitle>
                    <CardBody>
                      <Text component="h2" style={{ fontSize: '2rem', fontWeight: 600 }}>
                        {stat.value}
                      </Text>
                    </CardBody>
                  </Card>
                </GalleryItem>
              ))}
            </Gallery>

            {/* Recent Activities */}
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>Recent Activities</CardTitle>
              <CardBody>
                {recentActivities?.activities.length ? (
                  <DescriptionList isHorizontal>
                    {recentActivities.activities.map((activity) => (
                      <DescriptionListGroup key={activity.id}>
                        <DescriptionListTerm>
                          <strong>{activity.ticket_key}</strong>
                          <Text component="small" style={{ marginLeft: '0.5rem' }}>
                            {activity.action_type}
                          </Text>
                        </DescriptionListTerm>
                        <DescriptionListDescription>
                          {activity.ticket_summary || 'No summary'}
                          <Text component="small" style={{ display: 'block', color: 'var(--pf-v6-global--Color--200)' }}>
                            {format(new Date(activity.timestamp), 'MMM d, yyyy h:mm a')}
                          </Text>
                        </DescriptionListDescription>
                      </DescriptionListGroup>
                    ))}
                  </DescriptionList>
                ) : (
                  <Text>No recent activities</Text>
                )}
              </CardBody>
            </Card>

            {/* Projects Activity */}
            {activitySummary && Object.keys(activitySummary.by_project).length > 0 && (
              <Card style={{ marginTop: '1rem' }}>
                <CardTitle>Activity by Project</CardTitle>
                <CardBody>
                  <DescriptionList isHorizontal>
                    {Object.entries(activitySummary.by_project).map(([project, count]) => (
                      <DescriptionListGroup key={project}>
                        <DescriptionListTerm>{project}</DescriptionListTerm>
                        <DescriptionListDescription>
                          {count} activities
                        </DescriptionListDescription>
                      </DescriptionListGroup>
                    ))}
                  </DescriptionList>
                </CardBody>
              </Card>
            )}

            {/* Recent Reports */}
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>Recent Weekly Reports</CardTitle>
              <CardBody>
                {recentReports?.reports.length ? (
                  <DescriptionList>
                    {recentReports.reports.map((report) => (
                      <DescriptionListGroup key={report.id}>
                        <DescriptionListTerm>{report.title}</DescriptionListTerm>
                        <DescriptionListDescription>
                          {report.tickets_count} tickets | {report.projects.join(', ') || 'No projects'}
                        </DescriptionListDescription>
                      </DescriptionListGroup>
                    ))}
                  </DescriptionList>
                ) : (
                  <Text>No reports yet</Text>
                )}
              </CardBody>
            </Card>
          </>
        )}
      </PageSection>
    </>
  );
}

export default DashboardPage;

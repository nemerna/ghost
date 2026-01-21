/**
 * Team Dashboard page - overview of team activities (manager only)
 */

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  CardBody,
  CardTitle,
  Content,
  DescriptionList,
  DescriptionListDescription,
  DescriptionListGroup,
  DescriptionListTerm,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
  Gallery,
  GalleryItem,
  PageSection,
  Spinner,
  Title,
} from '@patternfly/react-core';
import { UsersIcon, ClipboardCheckIcon, CodeIcon } from '@patternfly/react-icons';
import { listTeams, getTeam } from '@/api/teams';
import { getTeamActivitySummary } from '@/api/activities';

export function TeamDashboardPage() {
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);

  // Fetch teams
  const { data: teamsData, isLoading: teamsLoading } = useQuery({
    queryKey: ['teams'],
    queryFn: () => listTeams({ all_teams: true }),
  });

  // Fetch selected team details
  const { data: teamDetails, isLoading: teamLoading } = useQuery({
    queryKey: ['team', selectedTeamId],
    queryFn: () => getTeam(selectedTeamId!),
    enabled: !!selectedTeamId,
  });

  // Fetch team activity summary
  const { data: activitySummary, isLoading: activityLoading } = useQuery({
    queryKey: ['teamActivitySummary', selectedTeamId],
    queryFn: () => getTeamActivitySummary(selectedTeamId!, 7),
    enabled: !!selectedTeamId,
  });

  const isLoading = teamsLoading || (selectedTeamId && (teamLoading || activityLoading));

  // Auto-select first team
  useEffect(() => {
    if (teamsData?.teams.length && !selectedTeamId) {
      setSelectedTeamId(teamsData.teams[0].id);
    }
  }, [teamsData, selectedTeamId]);

  return (
    <>
      <PageSection>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }}>
          <FlexItem>
            <Content>
              <Title headingLevel="h1">Team Dashboard</Title>
            </Content>
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
              <p>Please select a team to view the dashboard.</p>
            </CardBody>
          </Card>
        ) : (
          <>
            {/* Team Stats */}
            <Gallery hasGutter minWidths={{ default: '250px' }}>
              <GalleryItem>
                <Card>
                  <CardTitle>
                    <Flex>
                      <FlexItem><UsersIcon /></FlexItem>
                      <FlexItem>Team Members</FlexItem>
                    </Flex>
                  </CardTitle>
                  <CardBody>
                    <span style={{ fontSize: '2rem', fontWeight: 600 }}>
                      {teamDetails?.members.length || 0}
                    </span>
                  </CardBody>
                </Card>
              </GalleryItem>
              <GalleryItem>
                <Card>
                  <CardTitle>
                    <Flex>
                      <FlexItem><ClipboardCheckIcon /></FlexItem>
                      <FlexItem>Total Activities (7d)</FlexItem>
                    </Flex>
                  </CardTitle>
                  <CardBody>
                    <span style={{ fontSize: '2rem', fontWeight: 600 }}>
                      {(activitySummary as { total_activities?: number })?.total_activities || 0}
                    </span>
                  </CardBody>
                </Card>
              </GalleryItem>
              <GalleryItem>
                <Card>
                  <CardTitle>
                    <Flex>
                      <FlexItem><CodeIcon /></FlexItem>
                      <FlexItem>Unique Tickets (7d)</FlexItem>
                    </Flex>
                  </CardTitle>
                  <CardBody>
                    <span style={{ fontSize: '2rem', fontWeight: 600 }}>
                      {(activitySummary as { total_unique_tickets?: number })?.total_unique_tickets || 0}
                    </span>
                  </CardBody>
                </Card>
              </GalleryItem>
            </Gallery>

            {/* Team Members */}
            <Card style={{ marginTop: '1rem' }}>
              <CardTitle>Team Members</CardTitle>
              <CardBody>
                {teamDetails?.members.length ? (
                  <DescriptionList isHorizontal>
                    {teamDetails.members.map((member) => (
                      <DescriptionListGroup key={member.id}>
                        <DescriptionListTerm>
                          {member.display_name || member.email}
                        </DescriptionListTerm>
                        <DescriptionListDescription>
                          {member.email} | {member.role}
                          {(activitySummary as { by_member?: Record<string, { total_activities?: number }> })?.by_member?.[member.email] && (
                            <small style={{ marginLeft: '0.5rem' }}>
                              ({(activitySummary as { by_member?: Record<string, { total_activities?: number }> }).by_member?.[member.email]?.total_activities || 0} activities)
                            </small>
                          )}
                        </DescriptionListDescription>
                      </DescriptionListGroup>
                    ))}
                  </DescriptionList>
                ) : (
                  <p>No team members</p>
                )}
              </CardBody>
            </Card>

            {/* Activity by Action Type */}
            {activitySummary && (activitySummary as Record<string, Record<string, number>>).by_action_type && (
              <Card style={{ marginTop: '1rem' }}>
                <CardTitle>Activity by Type (Last 7 Days)</CardTitle>
                <CardBody>
                  <DescriptionList isHorizontal>
                    {Object.entries((activitySummary as Record<string, Record<string, number>>).by_action_type).map(([action, count]) => (
                      <DescriptionListGroup key={action}>
                        <DescriptionListTerm>{action}</DescriptionListTerm>
                        <DescriptionListDescription>{count}</DescriptionListDescription>
                      </DescriptionListGroup>
                    ))}
                  </DescriptionList>
                </CardBody>
              </Card>
            )}
          </>
        )}
      </PageSection>
    </>
  );
}

export default TeamDashboardPage;

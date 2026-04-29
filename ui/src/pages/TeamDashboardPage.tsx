import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  CardBody,
  Content,
  Dropdown,
  DropdownItem,
  DropdownList,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
  Grid,
  GridItem,
  Icon,
  Label,
  MenuToggle,
  PageSection,
  Spinner,
  Title,
} from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr } from '@patternfly/react-table';
import {
  BundleIcon,
  EllipsisVIcon,
  ListIcon,
  UsersIcon,
} from '@patternfly/react-icons';
import t_global_text_color_subtle from '@patternfly/react-tokens/dist/esm/t_global_text_color_subtle';
import { listTeams, getTeam, removeTeamMember } from '@/api/teams';
import { getTeamActivitySummary } from '@/api/activities';
import { NONSTATUS_COLORS } from '@/utils/colors';
import type { UserRole } from '@/types';

const ROLE_COLORS: Record<UserRole, 'purple' | 'blue' | 'grey'> = {
  admin: 'purple',
  manager: 'blue',
  user: 'grey',
};

const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Admin',
  manager: 'Manager',
  user: 'User',
};

const STAT_CARDS = [
  { key: 'members', title: 'Team Members', icon: UsersIcon, color: 'var(--pf-t--global--color--nonstatus--blue--default)' },
  { key: 'activities', title: 'Total Activities', icon: BundleIcon, color: 'var(--pf-t--global--color--nonstatus--green--default)' },
  { key: 'tickets', title: 'Unique Tickets', icon: ListIcon, color: 'var(--pf-t--global--color--nonstatus--purple--default)' },
] as const;

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function getInitials(name: string | null, email: string): string {
  if (name) {
    return name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}

function getSparklineBars(email: string, count: number, maxCount: number): number[] {
  const hash = hashString(email);
  const scale = maxCount > 0 ? count / maxCount : 0;
  return Array.from({ length: 5 }, (_, i) => {
    const base = Math.abs(Math.sin(hash + i * 1.7)) * 0.6 + 0.2;
    return Math.max(15, base * scale * 100);
  });
}

export function TeamDashboardPage() {
  const queryClient = useQueryClient();
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [openKebabId, setOpenKebabId] = useState<number | null>(null);

  const removeMemberMutation = useMutation({
    mutationFn: (memberId: number) => removeTeamMember(selectedTeamId!, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team', selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ['teamActivitySummary', selectedTeamId] });
    },
  });

  const { data: teamsData, isLoading: teamsLoading } = useQuery({
    queryKey: ['teams'],
    queryFn: () => listTeams({ all_teams: true }),
  });

  const { data: teamDetails, isLoading: teamLoading } = useQuery({
    queryKey: ['team', selectedTeamId],
    queryFn: () => getTeam(selectedTeamId!),
    enabled: !!selectedTeamId,
  });

  const { data: summary, isLoading: activityLoading } = useQuery({
    queryKey: ['teamActivitySummary', selectedTeamId],
    queryFn: () => getTeamActivitySummary(selectedTeamId!, { days: 7 }),
    enabled: !!selectedTeamId,
  });
  const isLoading = teamsLoading || (!!selectedTeamId && (teamLoading || activityLoading));

  useEffect(() => {
    if (teamsData?.teams.length && !selectedTeamId) {
      setSelectedTeamId(teamsData.teams[0].id);
    }
  }, [teamsData, selectedTeamId]);

  const maxActivity = !teamDetails?.members.length || !summary?.by_member
    ? 1
    : Math.max(1, ...teamDetails.members.map(m =>
        summary.by_member[m.email]?.total_activities || 0
      ));

  const statValues: Record<string, number> = {
    members: teamDetails?.members.length || 0,
    activities: summary?.total_activities || 0,
    tickets: summary?.total_unique_tickets || 0,
  };

  return (
    <>
      <PageSection>
        <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
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
            <FlexItem><Spinner size="xl" /></FlexItem>
          </Flex>
        ) : !selectedTeamId ? (
          <Card>
            <CardBody>
              <Content>Select a team to view the dashboard.</Content>
            </CardBody>
          </Card>
        ) : (
          <>
            <Grid hasGutter>
              {STAT_CARDS.map(({ key, title, icon: StatIcon, color }) => (
                <GridItem key={key} span={4}>
                  <Card isCompact>
                    <CardBody>
                      <Flex spaceItems={{ default: 'spaceItemsMd' }} alignItems={{ default: 'alignItemsCenter' }}>
                        <FlexItem>
                          <div style={{
                            width: '48px',
                            height: '48px',
                            borderRadius: 'var(--pf-t--global--border--radius--small)',
                            backgroundColor: `color-mix(in srgb, ${color} 10%, transparent)`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color,
                          }}>
                            <Icon size="lg">
                              <StatIcon />
                            </Icon>
                          </div>
                        </FlexItem>
                        <Flex direction={{ default: 'column' }} spaceItems={{ default: 'spaceItemsNone' }}>
                          <FlexItem>
                            <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                              {title}
                            </Content>
                          </FlexItem>
                          <FlexItem>
                            <Title headingLevel="h3" size="2xl" className="pf-v6-m-tabular-nums">
                              {statValues[key]}
                            </Title>
                          </FlexItem>
                        </Flex>
                      </Flex>
                    </CardBody>
                  </Card>
                </GridItem>
              ))}
            </Grid>

            <Card style={{ marginTop: 'var(--pf-t--global--spacer--lg)' }}>
              <CardBody>
                <Title headingLevel="h2" size="lg" style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}>
                  Team Members
                </Title>
                {teamDetails?.members.length ? (
                  <Table aria-label="Team roster" variant="compact">
                    <Thead>
                      <Tr>
                        <Th width={30}>Display name</Th>
                        <Th width={25}>Email Address</Th>
                        <Th width={15}>Role</Th>
                        <Th width={20}>Activity</Th>
                        <Th width={10} screenReaderText="Actions" />
                      </Tr>
                    </Thead>
                    <Tbody>
                      {teamDetails.members.map((member) => {
                        const count = summary?.by_member?.[member.email]?.total_activities || 0;
                        const bars = getSparklineBars(member.email, count, maxActivity);
                        const avatarColor = NONSTATUS_COLORS[hashString(member.email) % NONSTATUS_COLORS.length];
                        const initials = getInitials(member.display_name, member.email);

                        return (
                          <Tr key={member.id}>
                            <Td dataLabel="Member Name">
                              <Flex spaceItems={{ default: 'spaceItemsSm' }} alignItems={{ default: 'alignItemsCenter' }} flexWrap={{ default: 'nowrap' }}>
                                <FlexItem>
                                  <div style={{
                                    width: '32px',
                                    height: '32px',
                                    borderRadius: '50%',
                                    backgroundColor: avatarColor,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: '#fff',
                                    fontSize: 'var(--pf-t--global--font--size--body--sm)',
                                    fontWeight: 600,
                                    flexShrink: 0,
                                  }}>
                                    {initials}
                                  </div>
                                </FlexItem>
                                <FlexItem>
                                  {member.display_name || member.email.split('@')[0]}
                                </FlexItem>
                              </Flex>
                            </Td>
                            <Td dataLabel="Email Address">{member.email}</Td>
                            <Td dataLabel="Role">
                              <Label color={ROLE_COLORS[member.role]} isCompact>
                                {ROLE_LABELS[member.role]}
                              </Label>
                            </Td>
                            <Td dataLabel="Activity">
                              <Flex spaceItems={{ default: 'spaceItemsMd' }} alignItems={{ default: 'alignItemsCenter' }}>
                                <FlexItem>
                                  <span style={{ fontWeight: 600, minWidth: '1.5rem', display: 'inline-block' }} className="pf-v6-m-tabular-nums">
                                    {count}
                                  </span>
                                </FlexItem>
                                <FlexItem>
                                  <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '16px' }}>
                                    {bars.map((height, i) => (
                                      <div
                                        key={i}
                                        style={{
                                          width: '3px',
                                          height: `${height}%`,
                                          backgroundColor: 'var(--pf-t--global--color--brand--default)',
                                          borderRadius: '1px',
                                        }}
                                      />
                                    ))}
                                  </div>
                                </FlexItem>
                              </Flex>
                            </Td>
                            <Td dataLabel="Actions" isActionCell>
                              <Dropdown
                                isOpen={openKebabId === member.id}
                                onOpenChange={(isOpen) => setOpenKebabId(isOpen ? member.id : null)}
                                onSelect={() => setOpenKebabId(null)}
                                toggle={(toggleRef) => (
                                  <MenuToggle
                                    ref={toggleRef}
                                    variant="plain"
                                    onClick={() => setOpenKebabId(openKebabId === member.id ? null : member.id)}
                                    isExpanded={openKebabId === member.id}
                                    aria-label={`Actions for ${member.display_name || member.email}`}
                                  >
                                    <EllipsisVIcon />
                                  </MenuToggle>
                                )}
                                popperProps={{ position: 'right' }}
                              >
                                <DropdownList>
                                  <DropdownItem
                                    key="unassign"
                                    onClick={() => removeMemberMutation.mutate(member.id)}
                                    style={{ color: 'var(--pf-t--global--text--color--status--danger--default)' }}
                                  >
                                    Unassign from team
                                  </DropdownItem>
                                </DropdownList>
                              </Dropdown>
                            </Td>
                          </Tr>
                        );
                      })}
                    </Tbody>
                  </Table>
                ) : (
                  <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                    No team members
                  </Content>
                )}
              </CardBody>
            </Card>
          </>
        )}
      </PageSection>
    </>
  );
}

export default TeamDashboardPage;

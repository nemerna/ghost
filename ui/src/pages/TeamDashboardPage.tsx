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
  CheckCircleIcon,
  EllipsisVIcon,
  ExclamationCircleIcon,
  FileAltIcon,
  UsersIcon,
} from '@patternfly/react-icons';
import t_global_text_color_subtle from '@patternfly/react-tokens/dist/esm/t_global_text_color_subtle';
import { listTeams, getTeam, removeTeamMember } from '@/api/teams';
import { getTeamReportingProgress } from '@/api/reports';
import { NONSTATUS_COLORS, ROLE_COLORS, ROLE_LABELS } from '@/utils/colors';

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

export function TeamDashboardPage() {
  const queryClient = useQueryClient();
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [openKebabId, setOpenKebabId] = useState<number | null>(null);

  const removeMemberMutation = useMutation({
    mutationFn: (memberId: number) => removeTeamMember(selectedTeamId!, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team', selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ['teamReportingProgress', selectedTeamId] });
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

  const { data: reportingProgress, isLoading: progressLoading } = useQuery({
    queryKey: ['teamReportingProgress', selectedTeamId],
    queryFn: () => getTeamReportingProgress(selectedTeamId!),
    enabled: !!selectedTeamId,
  });

  const isLoading = teamsLoading || (!!selectedTeamId && (teamLoading || progressLoading));

  useEffect(() => {
    if (teamsData?.teams.length && !selectedTeamId) {
      setSelectedTeamId(teamsData.teams[0].id);
    }
  }, [teamsData, selectedTeamId]);

  const memberCount = teamDetails?.members.length ?? 0;
  const reportsSubmitted = reportingProgress?.members.filter(m => m.status === 'done').length ?? 0;
  const reportsMissing = reportingProgress?.members.filter(m => m.status === 'missing').length ?? 0;
  const reportsInProgress = reportingProgress?.members.filter(m => m.status === 'in_progress').length ?? 0;

  const STAT_CARDS = [
    {
      key: 'members',
      title: 'Team Members',
      value: memberCount,
      icon: UsersIcon,
      color: 'var(--pf-t--global--color--nonstatus--blue--default)',
    },
    {
      key: 'reports',
      title: 'Reports Submitted',
      value: reportsSubmitted,
      icon: CheckCircleIcon,
      color: 'var(--pf-t--global--color--status--success--default)',
    },
    {
      key: 'missing',
      title: 'Missing Report',
      value: reportsMissing,
      icon: ExclamationCircleIcon,
      color: 'var(--pf-t--global--color--status--warning--default)',
    },
    {
      key: 'in-progress',
      title: 'In Progress',
      value: reportsInProgress,
      icon: FileAltIcon,
      color: 'var(--pf-t--global--color--nonstatus--purple--default)',
    },
  ] as const;

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
              {STAT_CARDS.map(({ key, title, value, icon: StatIcon, color }) => (
                <GridItem key={key} span={3}>
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
                              {value}
                            </Title>
                          </FlexItem>
                        </Flex>
                      </Flex>
                    </CardBody>
                  </Card>
                </GridItem>
              ))}
            </Grid>

            <div style={{ marginTop: 'var(--pf-t--global--spacer--lg)' }}>
              <Title headingLevel="h2" size="lg" style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}>
                Team Members
              </Title>
              {teamDetails?.members.length ? (
                  <Table aria-label="Team roster" variant="compact">
                    <Thead>
                      <Tr>
                        <Th width={30}>Display name</Th>
                        <Th width={30}>Email Address</Th>
                        <Th width={15}>Role</Th>
                        <Th width={15}>Report Status</Th>
                        <Th width={10} screenReaderText="Actions" />
                      </Tr>
                    </Thead>
                    <Tbody>
                      {[...teamDetails.members].sort((a, b) => a.email.localeCompare(b.email)).map((member) => {
                        const progress = reportingProgress?.members.find(m => m.email === member.email);
                        const status = progress?.status ?? 'missing';
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
                            <Td dataLabel="Report Status">
                              <Label
                                color={status === 'done' ? 'green' : status === 'in_progress' ? 'blue' : 'orange'}
                                isCompact
                              >
                                {status === 'done' ? 'Submitted' : status === 'in_progress' ? 'In Progress' : 'Missing'}
                              </Label>
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
            </div>
          </>
        )}
      </PageSection>
    </>
  );
}

export default TeamDashboardPage;

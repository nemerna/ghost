/**
 * Dashboard page - shows management report summary and quick stats
 */

import { useMemo } from 'react';
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
  ClipboardListIcon,
  FileAltIcon,
  ListIcon,
  LockIcon,
} from '@patternfly/react-icons';
import t_global_text_color_subtle from '@patternfly/react-tokens/dist/esm/t_global_text_color_subtle';
import { useAuth } from '@/auth';
import { listManagementReports } from '@/api/reports';
import type { ManagementReport, ReportEntry } from '@/types';
import { NONSTATUS_COLORS } from '@/utils/colors';
import { format } from 'date-fns';

function parseEntries(report: ManagementReport): ReportEntry[] {
  try {
    const data = JSON.parse(report.content ?? '{}');
    if (data?.format === 'structured' && Array.isArray(data.entries)) {
      return data.entries as ReportEntry[];
    }
  } catch {
    // legacy plain-text content — no structured entries
  }
  return [];
}

const STAT_CARDS = [
  { key: 'reports', title: 'Reports', subtitle: 'Total saved', icon: FileAltIcon },
  { key: 'entries', title: 'Entries', subtitle: 'Across all reports', icon: ListIcon },
  { key: 'shared', title: 'Shared', subtitle: 'Visible to manager', icon: ClipboardListIcon },
  { key: 'private', title: 'Private', subtitle: 'Hidden from manager', icon: LockIcon },
] as const;

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: reportsData, isLoading } = useQuery({
    queryKey: ['managementReports', 'dashboard'],
    queryFn: () => listManagementReports({ limit: 20 }),
  });

  const reports = reportsData?.reports ?? [];

  const allEntries = useMemo(
    () => reports.flatMap((r) => parseEntries(r)),
    [reports],
  );

  const sharedCount = allEntries.filter((e) => !e.private).length;
  const privateCount = allEntries.filter((e) => e.private).length;

  const statValues: Record<string, number> = {
    reports: reports.length,
    entries: allEntries.length,
    shared: sharedCount,
    private: privateCount,
  };

  // Top projects by entry count
  // Recent entries from the most recent report
  const latestReport = reports[0];
  const recentEntries = latestReport ? parseEntries(latestReport).slice(0, 5) : [];

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

            {/* Bottom left — Recent Entries (8 cols) */}
            <GridItem span={8}>
              <Card>
                <CardBody>
                  <Flex
                    justifyContent={{ default: 'justifyContentSpaceBetween' }}
                    alignItems={{ default: 'alignItemsCenter' }}
                    style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}
                  >
                    <FlexItem>
                      <Title headingLevel="h2" size="lg">
                        {latestReport
                          ? `Recent Entries — ${latestReport.title}`
                          : 'Recent Entries'}
                      </Title>
                    </FlexItem>
                    <FlexItem>
                      <Button variant="link" isInline onClick={() => navigate('/management-reports')}>
                        View all reports
                      </Button>
                    </FlexItem>
                  </Flex>
                  {recentEntries.length ? (
                    <Table aria-label="Recent entries" variant="compact">
                      <Thead>
                        <Tr>
                          <Th width={10}>Visibility</Th>
                          <Th width={70}>Entry</Th>
                          <Th width={20}>Ticket</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {recentEntries.map((entry, idx) => (
                          <Tr key={idx}>
                            <Td dataLabel="Visibility">
                              <Label color={entry.private ? 'orange' : 'green'} isCompact>
                                {entry.private ? 'Private' : 'Shared'}
                              </Label>
                            </Td>
                            <Td dataLabel="Entry" modifier="truncate">
                              <span dangerouslySetInnerHTML={{ __html: entry.text }} />
                            </Td>
                            <Td dataLabel="Ticket" modifier="nowrap">
                              {entry.ticket_key ?? '-'}
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  ) : (
                    <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                      {reports.length === 0 ? 'No reports yet' : 'No structured entries in the latest report'}
                    </Content>
                  )}
                </CardBody>
              </Card>
            </GridItem>

            {/* Bottom right — Recent Reports (4 cols) */}
            <GridItem span={4}>
              <Card style={{ height: '100%' }}>
                <CardBody>
                  <Title headingLevel="h2" size="lg" style={{ marginBottom: 'var(--pf-t--global--spacer--md)' }}>
                    Recent Reports
                  </Title>
                  {reports.slice(0, 5).length > 0 ? (
                    reports.slice(0, 5).map((report, i) => {
                      const color = NONSTATUS_COLORS[i % NONSTATUS_COLORS.length];
                      const isLast = i === Math.min(reports.length, 5) - 1;
                      const entryCount = parseEntries(report).length;
                      return (
                        <div
                          key={report.id}
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
                              <Button
                                variant="link"
                                isInline
                                onClick={() => navigate('/management-reports')}
                                style={{ textAlign: 'left', whiteSpace: 'normal', wordBreak: 'break-word' }}
                              >
                                {report.title}
                              </Button>
                            </FlexItem>
                            <FlexItem>
                              <span style={{ color: t_global_text_color_subtle.var }}>
                                {entryCount} {entryCount === 1 ? 'entry' : 'entries'}
                              </span>
                            </FlexItem>
                          </Flex>
                          {report.created_at && (
                            <Content component="small" style={{ color: t_global_text_color_subtle.var, marginLeft: '16px' }}>
                              {format(new Date(report.created_at), 'MMM d, yyyy')}
                            </Content>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <Content component="small" style={{ color: t_global_text_color_subtle.var }}>
                      No reports yet
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

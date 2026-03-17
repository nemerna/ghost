import type { Activity } from '@/types';

/**
 * Build a browsable URL for a ticket from its source, key, and (for Jira) the
 * user's configured Jira server URL.
 *
 * Returns null when a URL cannot be constructed (e.g. Jira server URL missing).
 */
export function getTicketUrl(
  activity: Pick<Activity, 'ticket_source' | 'ticket_key' | 'project_key' | 'github_repo'>,
  jiraServerUrl?: string,
): string | null {
  if (activity.ticket_source === 'github') {
    const match = activity.ticket_key.match(/^([^#]+)#(\d+)$/);
    if (match) {
      const [, repo, issueNumber] = match;
      return `https://github.com/${repo}/issues/${issueNumber}`;
    }
  } else if (activity.ticket_source === 'jira') {
    const baseUrl = jiraServerUrl?.replace(/\/+$/, '');
    if (baseUrl) {
      return `${baseUrl}/browse/${activity.ticket_key}`;
    }
  }
  return null;
}

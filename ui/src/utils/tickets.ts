import type { Activity } from '@/types';

/**
 * Build a browsable URL for a ticket. Prefers the stored `ticket_url` from the
 * backend (set at log time from jira_get_issue / GitHub API). Falls back to
 * constructing a URL from the ticket key and source for older activities that
 * don't have a stored URL.
 */
export function getTicketUrl(
  activity: Pick<Activity, 'ticket_source' | 'ticket_key' | 'ticket_url' | 'project_key' | 'github_repo'>,
  jiraServerUrl?: string,
): string | null {
  if (activity.ticket_url) {
    return activity.ticket_url;
  }

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

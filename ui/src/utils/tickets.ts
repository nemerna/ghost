type TicketSource = 'jira' | 'github';

interface TicketRef {
  ticket_source?: TicketSource | null;
  ticket_key: string;
  ticket_url?: string | null;
  project_key?: string | null;
  github_repo?: string | null;
}

/**
 * Build a browsable URL for a ticket. Prefers the stored `ticket_url` from the
 * backend. Falls back to constructing a URL from the ticket key and source for
 * older entries that don't have a stored URL.
 */
export function getTicketUrl(
  ticket: TicketRef,
  jiraServerUrl?: string,
): string | null {
  if (ticket.ticket_url) {
    return ticket.ticket_url;
  }

  if (ticket.ticket_source === 'github') {
    const match = ticket.ticket_key.match(/^([^#]+)#(\d+)$/);
    if (match) {
      const [, repo, issueNumber] = match;
      return `https://github.com/${repo}/issues/${issueNumber}`;
    }
  } else if (ticket.ticket_source === 'jira') {
    const baseUrl = jiraServerUrl?.replace(/\/+$/, '');
    if (baseUrl) {
      return `${baseUrl}/browse/${ticket.ticket_key}`;
    }
  }
  return null;
}

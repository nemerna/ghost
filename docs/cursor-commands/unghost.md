Make untracked work visible. Create a tracking ticket (Jira or GitHub Issue) for work that was already submitted without proper tracking (commits, PRs), then add a progress comment linking the actual work.

**ALWAYS use MCP server tools** for all Jira, GitHub, and work-reports operations. Never use CLI tools, direct API calls, or custom clients.

## Phase 1: Auto-Detect Work Context

Gather as much context as possible about what the user worked on:

1. **Git context** (run in terminal):
   - `git branch --show-current` — get current branch name
   - `git log --oneline -10` — recent commits on this branch
   - `git remote get-url origin` — identify the repo

2. **GitHub context** (MCP tools):
   - `github_get_current_user` — get the user's GitHub login
   - `github_search_prs(query="author:USERNAME head:BRANCH_NAME")` — find PRs for this branch
   - If a PR is found, get its details: `github_get_pr` for full info (title, body, merge status, URL)
   - `github_get_pr_commits` — get commit list with SHAs and messages

3. **Session context**: consider any files the user has open, recent conversation, or anything they describe

4. **Present findings** to the user:
   - List the detected commits (with SHAs and messages)
   - List any PRs found (with URLs and status)
   - Summarize the work done based on commit messages / PR description
   - Ask the user to confirm this is the work they want to track, and to add any extra context

## Phase 2: Interactive Questions

Ask the user using structured questions:

1. **Where to create the ticket?**
   - Options: Jira / GitHub Issues

2. **If Jira:**
   - Ask which project (the user may know, or list options via `jira_list_projects`)
   - Ask which components — use `jira_list_components(project="PROJ")` to show available options
   - Ask for the issue type if relevant (Task, Story, Bug) — default to Task

3. **If GitHub Issues:**
   - Infer the repo from git remote, or ask the user to confirm/override
   - Ask for any labels to apply

## Phase 3: Create Ticket as a Request

The ticket MUST be written **as a request** — framed as what needs to be done, not as completed work. Even though the work is already submitted, write it as if requesting the work.

**Title**: A clean, request-style summary.
- Good: "Fix live consolidated report showing stale data from previous week"
- Bad: "Fixed the stale report bug" (past tense, sounds like done work)

**Body**: Describe the request:
- What is the problem or need?
- What should be done to address it?
- What are the acceptance criteria or expected outcome?

Write this based on the detected context (PR description, commit messages, user input). Do NOT mention that the work is already done in the ticket body — treat it purely as a request.

Use `jira_create_ticket` or `github_create_issue` depending on user's choice.

## Phase 4: Add Progress Comment

Immediately add a comment to the newly created ticket documenting the progress and resolution. This comment SHOULD reference the actual work:

**For GitHub issues**, use `github_add_issue_comment` with a body like:

```markdown
## Progress

[Implemented](PR-URL) this in commit [`SHORT_SHA`](COMMIT-URL).

**Status:** Merged / Open / In Review

**Commits:**
- [`abc1234`](COMMIT-URL) — commit message summary
- [`def5678`](COMMIT-URL) — commit message summary

**Pull Request:** [#NUMBER](PR-URL) — PR title
```

**For Jira tickets**, use `jira_add_comment` with equivalent content (using Jira wiki markup):

```
h2. Progress

[Implemented|PR-URL] this in commit [SHORT_SHA|COMMIT-URL].

*Status:* Merged / Open / In Review

*Commits:*
- [abc1234|COMMIT-URL] — commit message summary

*Pull Request:* [#NUMBER|PR-URL] — PR title
```

Include as much linked context as possible: commit SHAs, PR URLs, branch name, merge status.

## Phase 5: Optionally Log Activity

Ask the user: "Do you want to log this activity for your weekly report?"

If yes:
- Call `log_activity` with:
  - **ticket_key**: the created ticket key (`PROJ-123` or `owner/repo#123`)
  - **ticket_summary**: the ticket title
  - **action_type**: `create`
  - **jira_components**: include if Jira (from the components chosen earlier)
  - **github_repo**: include if GitHub (format: `owner/repo`)

## Summary of MCP Tools Used

| Phase | Tools |
|-------|-------|
| Detect | `github_get_current_user`, `github_search_prs`, `github_get_pr`, `github_get_pr_commits` |
| Create (Jira) | `jira_list_projects`, `jira_list_components`, `jira_create_ticket` |
| Create (GitHub) | `github_create_issue` |
| Comment (Jira) | `jira_add_comment` |
| Comment (GitHub) | `github_add_issue_comment` |
| Log | `log_activity` |

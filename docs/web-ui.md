# Web UI

Ghost includes a web dashboard built with PatternFly React for activity tracking and report management.

## Features Overview

### Dashboard

The main dashboard provides an overview of recent activity across all your tracked tickets and GitHub issues.

### Activities

View and search logged activities:

- Filter by date range, project, or ticket
- Clickable ticket links to Jira/GitHub
- Activity type indicators (created, updated, commented, etc.)

### My Reports

Personal weekly and management reports:

- View generated reports
- Edit report content
- Control visibility of individual entries

### Management Reports

Create and edit reports for stakeholders:

- **Inline editing**: View formatted markdown, click the pencil icon to edit raw text
- **Per-entry privacy**: Toggle the eye/lock icon to hide specific entries from managers
- Managers see filtered content (private entries hidden)

### Team Dashboard

Team activity overview (manager/admin only):

- Aggregate view of team member activities
- Project-level summaries
- Activity trends

### Team Reports

Team report management (manager/admin only):

- View team members' management reports
- Filter by project or time period
- Export capabilities

### Admin

User and team administration (admin only):

- User management: create, edit, disable users
- Team management: create teams, assign members
- Role assignment: user, manager, admin

### Settings

User preferences and visibility defaults:

- Default visibility for logged activities
- Notification preferences
- Display settings

### Dark Mode

Toggle between light and dark themes using the theme switcher in the navigation bar.

## Authentication

### OpenShift OAuth (Production)

In production, the UI integrates with OpenShift OAuth for single sign-on:

1. User accesses the application
2. OAuth proxy redirects to OpenShift login
3. After authentication, user is redirected back
4. User identity is passed via headers to the backend

### Development Mode

In development mode, authentication can be bypassed:

```bash
DEV_MODE=true
DEV_EMAIL=dev@example.com
```

This creates a development user automatically on first request.

## Role-Based Access

| Role | Capabilities |
|------|--------------|
| User | View own activities, create/edit own reports |
| Manager | User capabilities + view team activities and reports |
| Admin | Manager capabilities + user/team administration |

## API Integration

The web UI communicates with the REST API backend:

| Endpoint | Purpose |
|----------|---------|
| `/api/users/*` | User management |
| `/api/teams/*` | Team management |
| `/api/activities/*` | Activity CRUD |
| `/api/reports/*` | Report management |

## Technology Stack

- **React 18** - UI framework
- **PatternFly 5** - Red Hat design system
- **Vite** - Build tool and dev server
- **TypeScript** - Type safety

## See Also

- [Getting Started](getting-started.md) - Initial setup
- [Development](development.md) - Frontend development guide
- [Architecture](architecture.md) - System overview

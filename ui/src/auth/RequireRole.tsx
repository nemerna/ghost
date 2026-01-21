/**
 * Route guard component that requires specific roles
 */

import React from 'react';
import {
  Bullseye,
  EmptyState,
  EmptyStateBody,
  EmptyStateHeader,
  EmptyStateIcon,
} from '@patternfly/react-core';
import { LockIcon } from '@patternfly/react-icons';
import { useAuth } from './AuthContext';
import type { UserRole } from '@/types';

interface RequireRoleProps {
  children: React.ReactNode;
  roles: UserRole[];
  fallback?: React.ReactNode;
}

export function RequireRole({ children, roles, fallback }: RequireRoleProps) {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  if (!roles.includes(user.role)) {
    if (fallback) {
      return <>{fallback}</>;
    }

    return (
      <Bullseye>
        <EmptyState>
          <EmptyStateHeader
            titleText="Access Denied"
            icon={<EmptyStateIcon icon={LockIcon} />}
            headingLevel="h4"
          />
          <EmptyStateBody>
            You don't have permission to access this page.
            Required role: {roles.join(' or ')}.
          </EmptyStateBody>
        </EmptyState>
      </Bullseye>
    );
  }

  return <>{children}</>;
}

export default RequireRole;

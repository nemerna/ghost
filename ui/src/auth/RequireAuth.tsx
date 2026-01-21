/**
 * Route guard component that requires authentication
 */

import {
  Bullseye,
  EmptyState,
  EmptyStateBody,
  Spinner,
} from '@patternfly/react-core';
import { ExclamationCircleIcon } from '@patternfly/react-icons';
import { useAuth } from './AuthContext';

interface RequireAuthProps {
  children: React.ReactNode;
}

export function RequireAuth({ children }: RequireAuthProps) {
  const { user, loading, error } = useAuth();

  if (loading) {
    return (
      <Bullseye>
        <Spinner size="xl" />
      </Bullseye>
    );
  }

  if (error || !user) {
    return (
      <Bullseye>
        <EmptyState
          titleText="Authentication Required"
          icon={ExclamationCircleIcon}
          headingLevel="h4"
        >
          <EmptyStateBody>
            {error || 'Please log in to access this application.'}
          </EmptyStateBody>
        </EmptyState>
      </Bullseye>
    );
  }

  return <>{children}</>;
}

export default RequireAuth;

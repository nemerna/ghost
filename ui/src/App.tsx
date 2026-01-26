/**
 * Main application component with routing
 */

import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth, RequireRole } from '@/auth';
import { AppLayout } from '@/components/layout';

// Pages
import DashboardPage from '@/pages/DashboardPage';
import ActivitiesPage from '@/pages/ActivitiesPage';
import MyReportsPage from '@/pages/MyReportsPage';
import TeamDashboardPage from '@/pages/TeamDashboardPage';
import TeamReportsPage from '@/pages/TeamReportsPage';
import ManagementReportsPage from '@/pages/ManagementReportsPage';
import AdminUsersPage from '@/pages/AdminUsersPage';
import AdminTeamsPage from '@/pages/AdminTeamsPage';
import FieldsConfigPage from '@/pages/FieldsConfigPage';
import SettingsPage from '@/pages/SettingsPage';

function App() {
  return (
    <RequireAuth>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          {/* Default route */}
          <Route index element={<DashboardPage />} />
          
          {/* User routes */}
          <Route path="activities" element={<ActivitiesPage />} />
          <Route path="reports" element={<MyReportsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          
          {/* Manager routes */}
          <Route
            path="team"
            element={
              <RequireRole roles={['manager', 'admin']}>
                <TeamDashboardPage />
              </RequireRole>
            }
          />
          <Route
            path="team/reports"
            element={
              <RequireRole roles={['manager', 'admin']}>
                <TeamReportsPage />
              </RequireRole>
            }
          />
          <Route path="management-reports" element={<ManagementReportsPage />} />
          
          {/* Admin routes */}
          <Route
            path="admin/users"
            element={
              <RequireRole roles={['admin']}>
                <AdminUsersPage />
              </RequireRole>
            }
          />
          <Route
            path="admin/teams"
            element={
              <RequireRole roles={['admin']}>
                <AdminTeamsPage />
              </RequireRole>
            }
          />
          <Route
            path="admin/fields"
            element={
              <RequireRole roles={['admin']}>
                <FieldsConfigPage />
              </RequireRole>
            }
          />
          
          {/* Catch all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </RequireAuth>
  );
}

export default App;

/**
 * Settings page - user preferences
 */

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardTitle,
  Content,
  DescriptionList,
  DescriptionListDescription,
  DescriptionListGroup,
  DescriptionListTerm,
  Form,
  FormGroup,
  HelperText,
  HelperTextItem,
  PageSection,
  Switch,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { useAuth } from '@/auth';
import { updateMyPreferences, getMyVisibilitySettings, updateMyVisibilitySettings } from '@/api/users';
import type { VisibilitySettings } from '@/types';

export function SettingsPage() {
  const { user, refetchUser } = useAuth();
  const queryClient = useQueryClient();

  const [preferences, setPreferences] = useState({
    default_project: (user?.preferences?.default_project as string) || '',
    jira_server_url: (user?.preferences?.jira_server_url as string) || '',
  });

  const [successMessage, setSuccessMessage] = useState('');
  
  // Visibility settings state
  const [visibilitySettings, setVisibilitySettings] = useState<VisibilitySettings>({
    activity_logs: 'shared',
    weekly_reports: 'shared',
    management_reports: 'private',
  });

  // Fetch visibility settings
  const { data: visibilityData, isLoading: visibilityLoading } = useQuery({
    queryKey: ['visibilitySettings'],
    queryFn: getMyVisibilitySettings,
  });

  // Update local state when visibility data is fetched
  useEffect(() => {
    if (visibilityData?.visibility_defaults) {
      setVisibilitySettings(visibilityData.visibility_defaults);
    }
  }, [visibilityData]);

  const updateMutation = useMutation({
    mutationFn: () => updateMyPreferences(preferences),
    onSuccess: () => {
      refetchUser();
      setSuccessMessage('Preferences saved successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
    },
  });

  // Visibility settings mutation
  const visibilityMutation = useMutation({
    mutationFn: (settings: VisibilitySettings) => updateMyVisibilitySettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['visibilitySettings'] });
      setSuccessMessage('Visibility settings saved successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
    },
  });

  const handleSave = () => {
    updateMutation.mutate();
  };

  const handleVisibilitySave = () => {
    visibilityMutation.mutate(visibilitySettings);
  };

  const handleVisibilityToggle = (field: keyof VisibilitySettings) => {
    setVisibilitySettings((prev) => ({
      ...prev,
      [field]: prev[field] === 'shared' ? 'private' : 'shared',
    }));
  };

  return (
    <>
      <PageSection>
        <Content>
          <Title headingLevel="h1">Settings</Title>
        </Content>
      </PageSection>

      <PageSection>
        {successMessage && (
          <Alert variant="success" title={successMessage} style={{ marginBottom: '1rem' }} />
        )}

        {/* Profile Information */}
        <Card style={{ marginBottom: '1rem' }}>
          <CardTitle>Profile Information</CardTitle>
          <CardBody>
            <DescriptionList isHorizontal>
              <DescriptionListGroup>
                <DescriptionListTerm>Email</DescriptionListTerm>
                <DescriptionListDescription>{user?.email}</DescriptionListDescription>
              </DescriptionListGroup>
              <DescriptionListGroup>
                <DescriptionListTerm>Display Name</DescriptionListTerm>
                <DescriptionListDescription>
                  {user?.display_name || 'Not set'}
                </DescriptionListDescription>
              </DescriptionListGroup>
              <DescriptionListGroup>
                <DescriptionListTerm>Role</DescriptionListTerm>
                <DescriptionListDescription>{user?.role}</DescriptionListDescription>
              </DescriptionListGroup>
              <DescriptionListGroup>
                <DescriptionListTerm>First Seen</DescriptionListTerm>
                <DescriptionListDescription>
                  {user?.first_seen ? new Date(user.first_seen).toLocaleDateString() : '-'}
                </DescriptionListDescription>
              </DescriptionListGroup>
            </DescriptionList>
            <Content style={{ marginTop: '1rem' }}>
              <p>
                <em>Profile information is managed through OpenShift authentication.</em>
              </p>
            </Content>
          </CardBody>
        </Card>

        {/* Manager Visibility Settings */}
        <Card style={{ marginBottom: '1rem' }}>
          <CardTitle>Manager Visibility</CardTitle>
          <CardBody>
            <Content style={{ marginBottom: '1rem' }}>
              <p>
                Control what data your manager can see. These are your default settings.
                You can also override visibility for individual items.
              </p>
            </Content>
            <Form>
              <FormGroup fieldId="visibility-activities">
                <Switch
                  id="visibility-activities"
                  label="Activity Logs"
                  isChecked={visibilitySettings.activity_logs === 'shared'}
                  onChange={() => handleVisibilityToggle('activity_logs')}
                  isDisabled={visibilityLoading}
                />
                <HelperText>
                  <HelperTextItem>
                    {visibilitySettings.activity_logs === 'shared'
                      ? 'Your activity logs are visible to your manager by default'
                      : 'Your activity logs are hidden from your manager by default'}
                  </HelperTextItem>
                </HelperText>
              </FormGroup>
              <FormGroup fieldId="visibility-weekly">
                <Switch
                  id="visibility-weekly"
                  label="Weekly Reports"
                  isChecked={visibilitySettings.weekly_reports === 'shared'}
                  onChange={() => handleVisibilityToggle('weekly_reports')}
                  isDisabled={visibilityLoading}
                />
                <HelperText>
                  <HelperTextItem>
                    {visibilitySettings.weekly_reports === 'shared'
                      ? 'Your weekly reports are visible to your manager by default'
                      : 'Your weekly reports are hidden from your manager by default'}
                  </HelperTextItem>
                </HelperText>
              </FormGroup>
              <FormGroup fieldId="visibility-management">
                <Switch
                  id="visibility-management"
                  label="Management Reports"
                  isChecked={visibilitySettings.management_reports === 'shared'}
                  onChange={() => handleVisibilityToggle('management_reports')}
                  isDisabled={visibilityLoading}
                />
                <HelperText>
                  <HelperTextItem>
                    {visibilitySettings.management_reports === 'shared'
                      ? 'Your management reports are visible to your manager by default'
                      : 'Your management reports are hidden from your manager by default'}
                  </HelperTextItem>
                </HelperText>
              </FormGroup>
              <Button
                variant="primary"
                onClick={handleVisibilitySave}
                isLoading={visibilityMutation.isPending}
                isDisabled={visibilityLoading}
              >
                Save Visibility Settings
              </Button>
            </Form>
          </CardBody>
        </Card>

        {/* Preferences */}
        <Card>
          <CardTitle>Preferences</CardTitle>
          <CardBody>
            <Form>
              <FormGroup label="Default Project" fieldId="default-project">
                <TextInput
                  id="default-project"
                  value={preferences.default_project}
                  onChange={(_event, value) =>
                    setPreferences({ ...preferences, default_project: value })
                  }
                  placeholder="e.g., APPENG"
                />
              </FormGroup>
              <FormGroup label="Jira Server URL" fieldId="jira-server">
                <TextInput
                  id="jira-server"
                  value={preferences.jira_server_url}
                  onChange={(_event, value) =>
                    setPreferences({ ...preferences, jira_server_url: value })
                  }
                  placeholder="e.g., https://jira.example.com"
                />
              </FormGroup>
              <Button
                variant="primary"
                onClick={handleSave}
                isLoading={updateMutation.isPending}
              >
                Save Preferences
              </Button>
            </Form>
          </CardBody>
        </Card>
      </PageSection>
    </>
  );
}

export default SettingsPage;

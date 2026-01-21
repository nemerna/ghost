/**
 * Settings page - user preferences
 */

import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardTitle,
  DescriptionList,
  DescriptionListDescription,
  DescriptionListGroup,
  DescriptionListTerm,
  Form,
  FormGroup,
  PageSection,
  PageSectionVariants,
  TextContent,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { useAuth } from '@/auth';
import { updateMyPreferences } from '@/api/users';

export function SettingsPage() {
  const { user, refetchUser } = useAuth();
  const queryClient = useQueryClient();

  const [preferences, setPreferences] = useState({
    default_project: (user?.preferences?.default_project as string) || '',
    jira_server_url: (user?.preferences?.jira_server_url as string) || '',
  });

  const [successMessage, setSuccessMessage] = useState('');

  const updateMutation = useMutation({
    mutationFn: () => updateMyPreferences(preferences),
    onSuccess: () => {
      refetchUser();
      setSuccessMessage('Preferences saved successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
    },
  });

  const handleSave = () => {
    updateMutation.mutate();
  };

  return (
    <>
      <PageSection variant={PageSectionVariants.light}>
        <TextContent>
          <Title headingLevel="h1">Settings</Title>
        </TextContent>
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
            <TextContent style={{ marginTop: '1rem' }}>
              <p>
                <em>Profile information is managed through OpenShift authentication.</em>
              </p>
            </TextContent>
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

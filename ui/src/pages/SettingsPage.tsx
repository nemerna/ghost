/**
 * Settings page - user preferences and personal access tokens
 */

import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardTitle,
  ClipboardCopy,
  Content,
  DescriptionList,
  DescriptionListDescription,
  DescriptionListGroup,
  DescriptionListTerm,
  EmptyState,
  EmptyStateBody,
  Form,
  FormGroup,
  HelperText,
  HelperTextItem,
  Label,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  PageSection,
  Switch,
  TextInput,
  Title,
} from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr } from '@patternfly/react-table';
import { KeyIcon, TrashIcon } from '@patternfly/react-icons';
import { useAuth } from '@/auth';
import { updateMyPreferences, getMyVisibilitySettings, updateMyVisibilitySettings } from '@/api/users';
import { listTokens, createToken, revokeToken } from '@/api/tokens';
import type { VisibilitySettings, PersonalAccessTokenCreateResponse } from '@/types';

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

  // PAT state
  const [isCreateTokenModalOpen, setIsCreateTokenModalOpen] = useState(false);
  const [newTokenName, setNewTokenName] = useState('');
  const [newTokenExpiry, setNewTokenExpiry] = useState('');
  const [createdToken, setCreatedToken] = useState<PersonalAccessTokenCreateResponse | null>(null);
  const [tokenToRevoke, setTokenToRevoke] = useState<{ id: number; name: string } | null>(null);

  // Fetch visibility settings
  const { data: visibilityData, isLoading: visibilityLoading } = useQuery({
    queryKey: ['visibilitySettings'],
    queryFn: getMyVisibilitySettings,
  });

  // Fetch tokens
  const { data: tokensData, isLoading: tokensLoading } = useQuery({
    queryKey: ['personalAccessTokens'],
    queryFn: listTokens,
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

  // Create token mutation
  const createTokenMutation = useMutation({
    mutationFn: createToken,
    onSuccess: (data) => {
      setCreatedToken(data);
      setNewTokenName('');
      setNewTokenExpiry('');
      queryClient.invalidateQueries({ queryKey: ['personalAccessTokens'] });
    },
  });

  // Revoke token mutation
  const revokeTokenMutation = useMutation({
    mutationFn: (tokenId: number) => revokeToken(tokenId),
    onSuccess: () => {
      setTokenToRevoke(null);
      queryClient.invalidateQueries({ queryKey: ['personalAccessTokens'] });
      setSuccessMessage('Token revoked successfully!');
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

  const handleCreateToken = () => {
    createTokenMutation.mutate({
      name: newTokenName,
      expires_at: newTokenExpiry || null,
    });
  };

  const handleCloseCreateModal = () => {
    setIsCreateTokenModalOpen(false);
    setCreatedToken(null);
    setNewTokenName('');
    setNewTokenExpiry('');
    createTokenMutation.reset();
  };

  const tokens = tokensData?.tokens || [];

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

        {/* Personal Access Tokens */}
        <Card style={{ marginBottom: '1rem' }}>
          <CardTitle>
            <span style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              Personal Access Tokens
              <Button
                variant="primary"
                icon={<KeyIcon />}
                onClick={() => setIsCreateTokenModalOpen(true)}
                size="sm"
              >
                Create Token
              </Button>
            </span>
          </CardTitle>
          <CardBody>
            <Content style={{ marginBottom: '1rem' }}>
              <p>
                Personal access tokens are used to authenticate with the Reports MCP server.
                Configure your MCP client with the token in the <code>Authorization: Bearer &lt;token&gt;</code> header.
              </p>
            </Content>

            {tokensLoading ? (
              <Content><p>Loading tokens...</p></Content>
            ) : tokens.length === 0 ? (
              <EmptyState>
                <EmptyStateBody>
                  No personal access tokens yet. Create one to authenticate with the Reports MCP.
                </EmptyStateBody>
              </EmptyState>
            ) : (
              <Table aria-label="Personal access tokens" variant="compact">
                <Thead>
                  <Tr>
                    <Th>Name</Th>
                    <Th>Token</Th>
                    <Th>Created</Th>
                    <Th>Last Used</Th>
                    <Th>Expires</Th>
                    <Th>Status</Th>
                    <Th />
                  </Tr>
                </Thead>
                <Tbody>
                  {tokens.map((token) => {
                    const isExpired = token.expires_at && new Date(token.expires_at) <= new Date();
                    return (
                      <Tr key={token.id}>
                        <Td dataLabel="Name">{token.name}</Td>
                        <Td dataLabel="Token">
                          <code>{token.token_prefix}...</code>
                        </Td>
                        <Td dataLabel="Created">
                          {token.created_at ? new Date(token.created_at).toLocaleDateString() : '-'}
                        </Td>
                        <Td dataLabel="Last Used">
                          {token.last_used_at ? new Date(token.last_used_at).toLocaleString() : 'Never'}
                        </Td>
                        <Td dataLabel="Expires">
                          {token.expires_at ? new Date(token.expires_at).toLocaleDateString() : 'Never'}
                        </Td>
                        <Td dataLabel="Status">
                          {token.is_revoked ? (
                            <Label color="red">Revoked</Label>
                          ) : isExpired ? (
                            <Label color="orange">Expired</Label>
                          ) : (
                            <Label color="green">Active</Label>
                          )}
                        </Td>
                        <Td dataLabel="Actions" isActionCell>
                          {!token.is_revoked && (
                            <Button
                              variant="plain"
                              aria-label={`Revoke token ${token.name}`}
                              onClick={() => setTokenToRevoke({ id: token.id, name: token.name })}
                              icon={<TrashIcon />}
                              isDanger
                            />
                          )}
                        </Td>
                      </Tr>
                    );
                  })}
                </Tbody>
              </Table>
            )}
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

      {/* Create Token Modal */}
      <Modal
        isOpen={isCreateTokenModalOpen}
        onClose={handleCloseCreateModal}
        variant="medium"
      >
        <ModalHeader title={createdToken ? 'Token Created' : 'Create Personal Access Token'} />
        <ModalBody>
          {createdToken ? (
            <>
              <Alert
                variant="warning"
                title="Copy your token now"
                style={{ marginBottom: '1rem' }}
              >
                This is the only time you will see this token. Copy it and store it securely.
              </Alert>
              <FormGroup label="Token" fieldId="created-token">
                <ClipboardCopy
                  isReadOnly
                  hoverTip="Copy"
                  clickTip="Copied"
                  variant="expansion"
                >
                  {createdToken.token}
                </ClipboardCopy>
              </FormGroup>
              <Content style={{ marginTop: '1rem' }}>
                <p>
                  Use this token in your MCP client configuration:
                </p>
                <pre style={{ 
                  backgroundColor: 'var(--pf-t--global--background--color--secondary--default)',
                  padding: '0.75rem',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
                  overflowX: 'auto',
                }}>
{`{
  "mcpServers": {
    "work-reports": {
      "url": "https://<your-host>/mcp/reports",
      "headers": {
        "Authorization": "Bearer ${createdToken.token}"
      }
    }
  }
}`}
                </pre>
              </Content>
            </>
          ) : (
            <>
              {createTokenMutation.isError && (
                <Alert
                  variant="danger"
                  title={createTokenMutation.error?.message || 'Failed to create token'}
                  style={{ marginBottom: '1rem' }}
                />
              )}
              <Form>
                <FormGroup label="Token Name" isRequired fieldId="token-name">
                  <TextInput
                    id="token-name"
                    value={newTokenName}
                    onChange={(_event, value) => setNewTokenName(value)}
                    placeholder='e.g., "VS Code MCP" or "Cursor IDE"'
                    isRequired
                  />
                  <HelperText>
                    <HelperTextItem>
                      A descriptive name to help you identify this token later.
                    </HelperTextItem>
                  </HelperText>
                </FormGroup>
                <FormGroup label="Expiration Date" fieldId="token-expiry">
                  <TextInput
                    id="token-expiry"
                    type="date"
                    value={newTokenExpiry}
                    onChange={(_event, value) => setNewTokenExpiry(value)}
                  />
                  <HelperText>
                    <HelperTextItem>
                      Optional. Leave empty for a token that never expires.
                    </HelperTextItem>
                  </HelperText>
                </FormGroup>
              </Form>
            </>
          )}
        </ModalBody>
        <ModalFooter>
          {createdToken ? (
            <Button variant="primary" onClick={handleCloseCreateModal}>
              Done
            </Button>
          ) : (
            <>
              <Button
                variant="primary"
                onClick={handleCreateToken}
                isDisabled={!newTokenName.trim()}
                isLoading={createTokenMutation.isPending}
              >
                Create
              </Button>
              <Button variant="link" onClick={handleCloseCreateModal}>
                Cancel
              </Button>
            </>
          )}
        </ModalFooter>
      </Modal>

      {/* Revoke Token Confirmation Modal */}
      <Modal
        isOpen={!!tokenToRevoke}
        onClose={() => setTokenToRevoke(null)}
        variant="small"
      >
        <ModalHeader title="Revoke Token" />
        <ModalBody>
          Are you sure you want to revoke the token <strong>{tokenToRevoke?.name}</strong>?
          Any MCP clients using this token will no longer be able to authenticate.
        </ModalBody>
        <ModalFooter>
          <Button
            variant="danger"
            onClick={() => tokenToRevoke && revokeTokenMutation.mutate(tokenToRevoke.id)}
            isLoading={revokeTokenMutation.isPending}
          >
            Revoke
          </Button>
          <Button variant="link" onClick={() => setTokenToRevoke(null)}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default SettingsPage;

import { useState, useEffect } from 'react';
import {
  Button,
  Content,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  TextInput,
} from '@patternfly/react-core';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading?: boolean;
  /** The resource type label, e.g. "user", "team", "goal". Used in the title and body. */
  resourceType: string;
  /** The resource name the user must type to confirm deletion. */
  resourceName: string;
  /** Extra warning text shown below the main message. */
  warning?: string;
  /** Override the delete button label (default: "Delete"). */
  confirmLabel?: string;
}

/**
 * OpenShift-style destructive confirmation modal.
 *
 * Shows a danger dialog that asks the user to type the resource name before
 * the delete button becomes enabled — preventing accidental deletions.
 */
export function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading = false,
  resourceType,
  resourceName,
  warning,
  confirmLabel = 'Delete',
}: DeleteConfirmModalProps) {
  const [confirmInput, setConfirmInput] = useState('');

  useEffect(() => {
    if (!isOpen) setConfirmInput('');
  }, [isOpen]);

  const canConfirm = confirmInput === resourceName;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      aria-labelledby="delete-confirm-modal-title"
      aria-describedby="delete-confirm-modal-body"
      variant="small"
    >
      <ModalHeader
        title={`Delete ${resourceType}?`}
        labelId="delete-confirm-modal-title"
        titleIconVariant="danger"
      />
      <ModalBody id="delete-confirm-modal-body">
        <Content component="p" style={{ marginBottom: '1rem' }}>
          This action cannot be undone. All data associated with the {resourceType}{' '}
          <strong>{resourceName}</strong> will be permanently deleted.
        </Content>
        {warning && (
          <Content component="p" style={{ marginBottom: '1rem', color: 'var(--pf-t--global--text--color--status--danger--default)' }}>
            {warning}
          </Content>
        )}
        <Content component="p" style={{ marginBottom: '0.5rem' }}>
          Confirm deletion by typing <strong>{resourceName}</strong> below:
        </Content>
        <TextInput
          value={confirmInput}
          onChange={(_e, value) => setConfirmInput(value)}
          aria-label={`Type "${resourceName}" to confirm`}
          placeholder={resourceName}
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter' && canConfirm && !isLoading) onConfirm();
          }}
        />
      </ModalBody>
      <ModalFooter>
        <Button
          variant="danger"
          isLoading={isLoading}
          isDisabled={!canConfirm || isLoading}
          onClick={onConfirm}
        >
          {confirmLabel}
        </Button>
        <Button variant="link" onClick={onClose}>
          Cancel
        </Button>
      </ModalFooter>
    </Modal>
  );
}

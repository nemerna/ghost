import { Button, Modal, ModalBody, ModalFooter, ModalHeader } from '@patternfly/react-core';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isLoading?: boolean;
  /** Number of items being deleted — drives singular/plural title and message. Default: 1 */
  itemCount?: number;
  /** Override the generated body message entirely */
  message?: string;
  /** Override the generated title entirely */
  title?: string;
}

/**
 * Reusable danger confirmation modal following the PF6 warning modal pattern.
 * Use for any destructive delete action — single row, bulk, or cross-page.
 */
export function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading = false,
  itemCount = 1,
  message,
  title,
}: DeleteConfirmModalProps) {
  const defaultTitle =
    itemCount === 1 ? 'Delete item?' : `Delete ${itemCount} items?`;

  const defaultMessage =
    itemCount === 1
      ? 'Are you sure you want to delete this item? This action cannot be undone.'
      : `Are you sure you want to delete these ${itemCount} items? This action cannot be undone.`;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      aria-labelledby="delete-confirm-modal-title"
      aria-describedby="delete-confirm-modal-body"
      variant="small"
    >
      <ModalHeader
        title={title ?? defaultTitle}
        labelId="delete-confirm-modal-title"
        titleIconVariant="danger"
      />
      <ModalBody id="delete-confirm-modal-body">{message ?? defaultMessage}</ModalBody>
      <ModalFooter>
        <Button variant="danger" isLoading={isLoading} onClick={onConfirm}>
          Delete
        </Button>
        <Button variant="link" onClick={onClose}>
          Cancel
        </Button>
      </ModalFooter>
    </Modal>
  );
}

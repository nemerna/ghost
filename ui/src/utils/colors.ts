import type { UserRole } from '@/types';

export const ROLE_COLORS: Record<UserRole, 'purple' | 'blue' | 'grey'> = {
  admin: 'purple',
  manager: 'blue',
  user: 'grey',
};

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Admin',
  manager: 'Manager',
  user: 'User',
};

export const NONSTATUS_COLORS = [
  'var(--pf-t--global--color--nonstatus--blue--default)',
  'var(--pf-t--global--color--nonstatus--green--default)',
  'var(--pf-t--global--color--nonstatus--orange--default)',
  'var(--pf-t--global--color--nonstatus--purple--default)',
  'var(--pf-t--global--color--nonstatus--red--default)',
];

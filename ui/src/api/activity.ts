/**
 * Activity API — ticket activity derived from existing report entries.
 */

import apiClient from './client';
import type { TicketActivityResponse } from '@/types';

export async function getTicketActivity(params?: {
  team_id?: number;
  period_days?: number;
}): Promise<TicketActivityResponse> {
  const response = await apiClient.get<TicketActivityResponse>('/activity/tickets', { params });
  return response.data;
}

import type { ProfileApiRecord } from '@/types/profile';

/** Preference signal returned by GET /api/memory/signals. Backend is the source of truth. */
export type MemorySignalStatus = 'observed' | 'confirmed' | 'dismissed';

export interface MemorySignal {
  id: string;
  type: string;
  label: string;
  status: MemorySignalStatus;
  evidence_count: number;
  confidence: number;
}

export interface MemorySignalsResponse {
  signals: MemorySignal[];
}

export type MemoryPromotionStatus = 'promoted' | 'already_promoted' | 'already_covered';

export interface PromoteMemorySignalResponse {
  status: MemoryPromotionStatus;
  profile: ProfileApiRecord;
  profile_revision: number;
  signal_status: 'promoted';
  constraint_id?: string;
}

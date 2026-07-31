import { createContext } from 'react';
import type {
  LocalStrategyInputChangeReason,
  ServerPreviewStaleReason,
  StrategyInputChangeEvent,
  StrategyInputInvalidationEffect,
} from '@/features/strategy-inputs/types';

export interface StrategyInputsContextValue {
  /** Strategy inputs revision — bumps only on local input mutations. */
  revision: number;
  lastChange: StrategyInputChangeEvent | null;
  /** Subscriber signal for preview/compare; bumps for input invalidation and stale detection. */
  invalidationSeq: number;
  notifyStrategyInputsChanged(
    reason: LocalStrategyInputChangeReason,
  ): StrategyInputInvalidationEffect;
  notifyPreviewBecameStale(reason: ServerPreviewStaleReason): StrategyInputInvalidationEffect;
}

export const StrategyInputsContext = createContext<StrategyInputsContextValue | null>(null);

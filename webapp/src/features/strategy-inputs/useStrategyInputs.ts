import { useContext } from 'react';
import { StrategyInputsContext, type StrategyInputsContextValue } from '@/features/strategy-inputs/StrategyInputsContext';

export function useStrategyInputs(): StrategyInputsContextValue {
  const value = useContext(StrategyInputsContext);
  if (!value) {
    throw new Error('useStrategyInputs must be used within StrategyInputsProvider');
  }
  return value;
}

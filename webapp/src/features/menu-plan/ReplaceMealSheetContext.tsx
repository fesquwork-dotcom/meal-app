import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type FC,
  type ReactNode,
} from 'react';

import type { DayMeal } from '@/types/menu';

export interface ReplacementTarget {
  dayIndex: number;
  meal: DayMeal;
}

interface ReplaceMealSheetContextValue {
  isOpen: boolean;
  target: ReplacementTarget | null;
  openSheet: (target: ReplacementTarget) => void;
  closeSheet: () => void;
}

const ReplaceMealSheetContext = createContext<ReplaceMealSheetContextValue | null>(null);

export const ReplaceMealSheetProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [target, setTarget] = useState<ReplacementTarget | null>(null);

  const openSheet = useCallback((nextTarget: ReplacementTarget) => {
    setTarget(nextTarget);
    setIsOpen(true);
  }, []);

  const closeSheet = useCallback(() => {
    setIsOpen(false);
    setTarget(null);
  }, []);

  const value = useMemo(
    () => ({ isOpen, target, openSheet, closeSheet }),
    [isOpen, target, openSheet, closeSheet],
  );

  return (
    <ReplaceMealSheetContext.Provider value={value}>{children}</ReplaceMealSheetContext.Provider>
  );
};

export function useReplaceMealSheet(): ReplaceMealSheetContextValue {
  const context = useContext(ReplaceMealSheetContext);
  if (!context) {
    throw new Error('useReplaceMealSheet must be used within ReplaceMealSheetProvider');
  }
  return context;
}

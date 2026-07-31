import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type FC,
  type ReactNode,
} from 'react';

export interface GenerateMenuSheetContextValue {
  isOpen: boolean;
  openSheet: () => void;
  closeSheet: () => void;
}

const GenerateMenuSheetContext = createContext<GenerateMenuSheetContextValue | null>(null);

export interface GenerateMenuSheetProviderProps {
  children: ReactNode;
}

export const GenerateMenuSheetProvider: FC<GenerateMenuSheetProviderProps> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);

  const openSheet = useCallback(() => setIsOpen(true), []);
  const closeSheet = useCallback(() => setIsOpen(false), []);

  const value = useMemo(
    () => ({ isOpen, openSheet, closeSheet }),
    [isOpen, openSheet, closeSheet],
  );

  return (
    <GenerateMenuSheetContext.Provider value={value}>
      {children}
    </GenerateMenuSheetContext.Provider>
  );
};

export function useGenerateMenuSheet(): GenerateMenuSheetContextValue {
  const context = useContext(GenerateMenuSheetContext);

  if (!context) {
    throw new Error('useGenerateMenuSheet must be used within GenerateMenuSheetProvider');
  }

  return context;
}

import { useId, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Typography } from '@/components/ui/Typography';
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion';
import { cn } from '@/lib/utils';

export interface AccordionProps {
  title: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  badge?: ReactNode;
}

export function Accordion({
  title,
  children,
  defaultOpen = false,
  className,
  badge,
}: AccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const prefersReducedMotion = usePrefersReducedMotion();
  const baseId = useId();
  const contentId = `${baseId}-content`;
  const buttonId = `${baseId}-button`;

  return (
    <div className={cn('border-t border-app-bg', className)}>
      <button
        id={buttonId}
        type="button"
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          'flex w-full items-center justify-between gap-2 py-3 text-left',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link focus-visible:ring-offset-2 focus-visible:ring-offset-app-secondary',
        )}
      >
        <span className="flex min-w-0 flex-1 items-center gap-2">
          <Typography variant="label" className="truncate">
            {title}
          </Typography>
          {badge}
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-app-hint transition-transform duration-200',
            isOpen && 'rotate-180',
            prefersReducedMotion && 'transition-none',
          )}
          aria-hidden="true"
        />
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            id={contentId}
            role="region"
            aria-labelledby={buttonId}
            initial={prefersReducedMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={prefersReducedMotion ? undefined : { height: 0, opacity: 0 }}
            transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="pb-3">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

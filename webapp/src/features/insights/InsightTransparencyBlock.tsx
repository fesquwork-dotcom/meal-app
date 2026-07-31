import { useId, useState, type FC } from 'react';

import { Typography } from '@/components/ui';
import type {
  InsightTransparencyViewModel,
  TransparencyLineTone,
} from '@/features/insights/insightTransparencyViewModel';

function logTransparencyToggle(insightId: string, open: boolean): void {
  if (import.meta.env.DEV) {
    console.info(
      open ? 'insight_transparency_opened' : 'insight_transparency_closed',
      { insight: insightId },
    );
  }
}

const TONE_MARKS: Record<TransparencyLineTone, string> = {
  ok: '\u2713',
  warning: '\u26a0',
  neutral: '\u00b7',
};

export const InsightTransparencyBlock: FC<{
  insightId: string;
  transparency: InsightTransparencyViewModel;
}> = ({ insightId, transparency }) => {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();

  const toggle = () => {
    setIsOpen((previous) => {
      logTransparencyToggle(insightId, !previous);
      return !previous;
    });
  };

  return (
    <div className="mt-1">
      <button
        type="button"
        className="text-sm text-app-link underline-offset-2 hover:underline"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={toggle}
      >
        {transparency.toggleLabel}
      </button>
      <div id={panelId} hidden={!isOpen}>
        {isOpen ? (
          <ul className="mt-1.5 flex flex-col gap-1" role="list">
            {transparency.lines.map((line) => (
              <li key={line.id} className="flex items-start gap-1.5">
                <span aria-hidden="true" className="shrink-0">
                  {TONE_MARKS[line.tone]}
                </span>
                <Typography variant="caption" className="text-app-hint">
                  {line.text}
                </Typography>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
};

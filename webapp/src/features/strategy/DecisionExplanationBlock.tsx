import { useId, useState, type FC } from 'react';

import { Button, Typography } from '@/components/ui';
import { buildDecisionExplanationViewModel } from '@/features/strategy/decisionExplanationViewModel';
import type { DecisionExplanationCollection } from '@/types/decisionExplanation';

interface DecisionExplanationBlockProps {
  collection: DecisionExplanationCollection | null | undefined;
  compact?: boolean;
}

export const DecisionExplanationBlock: FC<DecisionExplanationBlockProps> = ({
  collection,
  compact = false,
}) => {
  const baseId = useId();
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const viewModel = buildDecisionExplanationViewModel(collection, compact ? false : showAll);

  if (!viewModel) return null;

  const visible = compact ? viewModel.visible.slice(0, 3) : viewModel.visible;
  const toggle = (key: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <section aria-labelledby={`${baseId}-heading`} className="flex flex-col gap-3">
      <div>
        <Typography id={`${baseId}-heading`} variant="h3">
          {compact ? 'Главные правила будущего плана' : viewModel.headline}
        </Typography>
        {!compact && (
          <Typography variant="caption" className="text-app-hint">
            {viewModel.summary}
          </Typography>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {visible.map((item) => {
          const isExpanded = compact ? false : expanded.has(item.decision_key);
          const regionId = `${baseId}-${item.decision_key.replaceAll('.', '-')}`;
          return (
            <div key={item.decision_key} className="rounded-app-lg bg-app-secondary p-3">
              {compact ? (
                <div className="flex flex-col gap-1">
                  <Typography variant="label">{item.title}</Typography>
                  <Typography variant="body">{item.outcome}</Typography>
                  <Typography variant="caption" className="text-app-hint">
                    {item.explanation}
                  </Typography>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    className="flex w-full items-start justify-between gap-3 text-left"
                    aria-expanded={isExpanded}
                    aria-controls={regionId}
                    onClick={() => toggle(item.decision_key)}
                  >
                    <span className="flex min-w-0 flex-col">
                      <Typography variant="label">{item.title}</Typography>
                      <Typography variant="body">{item.outcome}</Typography>
                    </span>
                    <span aria-hidden="true" className="text-app-hint">
                      {isExpanded ? '−' : '+'}
                    </span>
                  </button>
                  {isExpanded && (
                    <div
                      id={regionId}
                      role="region"
                      aria-label={item.title}
                      className="mt-2 flex flex-col gap-2 border-t border-app-secondary pt-2"
                    >
                      <Typography variant="body" className="text-app-hint">
                        {item.explanation}
                      </Typography>
                      {item.source_label && (
                        <Typography variant="caption">
                          Источник: {item.source_label}
                        </Typography>
                      )}
                      {item.confidence_label && (
                        <Typography variant="caption" className="text-app-hint">
                          {item.confidence_label}
                        </Typography>
                      )}
                      {item.supporting_points.length > 0 && (
                        <ul className="list-disc pl-5">
                          {item.supporting_points.map((point) => (
                            <li key={point}>
                              <Typography variant="caption">{point}</Typography>
                            </li>
                          ))}
                        </ul>
                      )}
                      {item.alternative_note && (
                        <Typography variant="caption" className="text-app-hint">
                          {item.alternative_note}
                        </Typography>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>

      {!compact && !showAll && viewModel.hiddenCount > 0 && (
        <Button type="button" variant="ghost" onClick={() => setShowAll(true)}>
          Показать остальные ({viewModel.hiddenCount})
        </Button>
      )}
    </section>
  );
};

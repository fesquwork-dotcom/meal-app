import { useCallback, useEffect, useRef, useState, type FC } from 'react';

import { compareStrategy } from '@/api/strategyCompare';
import { Button, Card, CardContent, Typography } from '@/components/ui';
import {
  buildStrategySettingsDiffViewModel,
  formatSettingChangeLine,
} from '@/features/strategy/strategySettingsDiffViewModel';
import { getStrategyInputInvalidationEffect } from '@/features/strategy-inputs/strategyInputInvalidation';
import { isCompareStale } from '@/features/strategy-inputs/strategyInvalidationCoalescing';
import { useStrategyInputs } from '@/features/strategy-inputs/useStrategyInputs';
import {
  classifyStrategyWorkflowError,
  routeStaleWorkflowError,
  StrategyWorkflowErrorPanel,
  workflowFailure,
  workflowSuccess,
} from '@/features/strategy-workflow';
import { isRequestAbortError } from '@/features/async-resource';
import type {
  GenerateMenuWorkflowResult,
  StrategyWorkflowError,
  WorkflowResult,
  WorkflowRetryAction,
} from '@/features/strategy-workflow/types';
import type { StrategyCompareResponse } from '@/types/strategyCompare';
import { buildDecisionCompareViewModel } from '@/features/strategy/decisionCompareViewModel';

export type StrategyCompareWorkflowResult = WorkflowResult<StrategyCompareResponse>;

interface StrategyCompareSectionProps {
  strategyId: string | null | undefined;
  planStartDate: string;
  hasProfileDraft: boolean;
  onGenerateWithToken?: (previewToken: string) => Promise<GenerateMenuWorkflowResult>;
  isGenerating?: boolean;
}

export const StrategyCompareSection: FC<StrategyCompareSectionProps> = ({
  strategyId,
  planStartDate,
  hasProfileDraft,
  onGenerateWithToken,
  isGenerating = false,
}) => {
  const {
    revision,
    lastChange,
    invalidationSeq,
    notifyStrategyInputsChanged,
    notifyPreviewBecameStale,
  } = useStrategyInputs();
  const [compareResult, setCompareResult] = useState<StrategyCompareResponse | null>(null);
  const [builtAtStrategyInputsRevision, setBuiltAtStrategyInputsRevision] = useState<number | null>(
    null,
  );
  const [isComparing, setIsComparing] = useState(false);
  const [compareError, setCompareError] = useState<StrategyWorkflowError | null>(null);
  const lastPlanStartDateRef = useRef(planStartDate);
  const planDateInitializedRef = useRef(false);
  const isComparingRef = useRef(false);
  const compareRequestIdRef = useRef(0);
  const compareControllerRef = useRef<AbortController | null>(null);
  const compareRef = useRef({
    result: compareResult as StrategyCompareResponse | null,
    builtAt: builtAtStrategyInputsRevision as number | null,
  });
  compareRef.current = { result: compareResult, builtAt: builtAtStrategyInputsRevision };

  useEffect(() => {
    return () => {
      compareControllerRef.current?.abort();
    };
  }, []);

  const clearCompare = useCallback(() => {
    setCompareResult(null);
    setBuiltAtStrategyInputsRevision(null);
    setCompareError(null);
  }, []);

  useEffect(() => {
    clearCompare();
  }, [hasProfileDraft, strategyId, clearCompare]);

  useEffect(() => {
    if (invalidationSeq === 0 || !lastChange) {
      return;
    }
    const effect = getStrategyInputInvalidationEffect(lastChange.reason);
    if (!effect.invalidateCompare) {
      return;
    }

    const current = compareRef.current;
    if (current.result == null) {
      return;
    }

    if (
      lastChange.kind === 'input_changed' &&
      !isCompareStale(
        {
          result: current.result,
          builtAtStrategyInputsRevision: current.builtAt,
        },
        revision,
      )
    ) {
      return;
    }

    clearCompare();
  }, [invalidationSeq, lastChange, revision, clearCompare]);

  useEffect(() => {
    if (!planDateInitializedRef.current) {
      planDateInitializedRef.current = true;
      lastPlanStartDateRef.current = planStartDate;
      return;
    }
    if (lastPlanStartDateRef.current === planStartDate) {
      return;
    }
    lastPlanStartDateRef.current = planStartDate;
    notifyStrategyInputsChanged('plan_start_date_changed');
  }, [planStartDate, notifyStrategyInputsChanged]);

  const handleCompare = useCallback(async (): Promise<StrategyCompareWorkflowResult> => {
    if (!strategyId || hasProfileDraft) {
      return workflowFailure(new Error('Сначала сохраните изменения профиля.'));
    }
    if (isComparingRef.current) {
      return workflowFailure(new Error('Сравнение уже выполняется.'));
    }

    const requestId = ++compareRequestIdRef.current;
    compareControllerRef.current?.abort();
    const controller = new AbortController();
    compareControllerRef.current = controller;
    isComparingRef.current = true;
    setIsComparing(true);
    setCompareError(null);
    try {
      const result = await compareStrategy(
        strategyId,
        { plan_start_date: planStartDate },
        { signal: controller.signal },
      );
      if (requestId !== compareRequestIdRef.current) {
        return workflowSuccess(result);
      }
      setCompareResult(result);
      setBuiltAtStrategyInputsRevision(revision);
      return workflowSuccess(result);
    } catch (error) {
      if (isRequestAbortError(error)) {
        // Abort is not a user-facing compare error.
        return { ok: false, error: classifyStrategyWorkflowError(error) };
      }
      if (requestId !== compareRequestIdRef.current) {
        return { ok: false, error: classifyStrategyWorkflowError(error) };
      }
      const classified = classifyStrategyWorkflowError(error);
      routeStaleWorkflowError(classified, notifyPreviewBecameStale);
      setCompareError(classified);
      setCompareResult(null);
      setBuiltAtStrategyInputsRevision(null);
      return { ok: false, error: classified };
    } finally {
      if (requestId === compareRequestIdRef.current) {
        isComparingRef.current = false;
        setIsComparing(false);
      }
    }
  }, [
    strategyId,
    hasProfileDraft,
    planStartDate,
    revision,
    notifyPreviewBecameStale,
  ]);

  const handleGenerate = useCallback(
    async (token: string) => {
      if (!onGenerateWithToken) {
        return;
      }
      setCompareError(null);
      const result = await onGenerateWithToken(token);
      if (result.ok) {
        return;
      }
      routeStaleWorkflowError(result.error, notifyPreviewBecameStale);
      if (result.error.kind !== 'stale') {
        setCompareError(result.error);
      }
    },
    [onGenerateWithToken, notifyPreviewBecameStale],
  );

  const handleErrorAction = (action: WorkflowRetryAction) => {
    if (action === 'retry_same_request' || action === 'build_new_preview') {
      void handleCompare();
    }
  };

  if (!strategyId) {
    return null;
  }

  const diffViewModel = buildStrategySettingsDiffViewModel(compareResult?.diff);
  const decisionViewModel = buildDecisionCompareViewModel(compareResult?.decision_changes);
  const preview = compareResult?.preview;
  const previewReady = preview?.status === 'ready' && Boolean(preview.preview_token);
  const previewConflict = preview?.status === 'conflict' && preview.conflicts.length > 0;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-4">
        <Typography variant="h3">Текущий и следующий план</Typography>
        {hasProfileDraft ? (
          <Typography variant="body" className="text-app-hint">
            Сначала сохраните изменения, чтобы сравнить планы.
          </Typography>
        ) : (
          <Button
            type="button"
            variant="secondary"
            size="full"
            disabled={isComparing}
            onClick={() => void handleCompare()}
          >
            {isComparing ? 'Сравниваем…' : 'Сравнить с текущим планом'}
          </Button>
        )}

        {compareError && (
          <StrategyWorkflowErrorPanel
            error={compareError}
            compact
            onAction={handleErrorAction}
            onDismiss={() => setCompareError(null)}
          />
        )}

        {previewConflict && (
          <Typography variant="body" className="text-app-hint" role="status">
            {preview.conflicts[0]?.description ??
              'Перед созданием нового плана нужно устранить противоречие в настройках.'}
          </Typography>
        )}

        {diffViewModel && !diffViewModel.unavailable && (
          <div className="flex flex-col gap-2" role="status">
            {diffViewModel.partialNotice && (
              <Typography variant="caption" className="text-app-hint">
                {diffViewModel.partialNotice}
              </Typography>
            )}
            <Typography variant="label">{diffViewModel.title}</Typography>
            {diffViewModel.changes.length > 0 && (
              <ul className="flex flex-col gap-2">
                {diffViewModel.changes.map((change) => (
                  <li key={change.key} className="flex gap-2">
                    <span aria-hidden="true" className="mt-1 text-app-accent">
                      •
                    </span>
                    <Typography variant="body" className="min-w-0">
                      {formatSettingChangeLine(change)}
                    </Typography>
                  </li>
                ))}
              </ul>
            )}
            {diffViewModel.unchangedLine && (
              <Typography variant="caption" className="text-app-hint">
                {diffViewModel.unchangedLine}
              </Typography>
            )}
          </div>
        )}

        {decisionViewModel && (
          <section className="flex flex-col gap-2" aria-labelledby="decision-changes-heading">
            <Typography id="decision-changes-heading" variant="label">
              {decisionViewModel.title}
            </Typography>
            {decisionViewModel.unchanged ? (
              <Typography variant="caption" className="text-app-hint">
                Причины основных решений не изменились.
              </Typography>
            ) : (
              <ul className="flex flex-col gap-2">
                {decisionViewModel.changes.map((change) => (
                  <li key={change.decision_key} className="rounded-app-lg bg-app-secondary p-3">
                    <Typography variant="label">{change.title}</Typography>
                    <Typography variant="body">
                      {change.before} → {change.after}
                    </Typography>
                    <Typography variant="caption" className="text-app-hint">
                      {change.explanation}
                    </Typography>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {previewReady && onGenerateWithToken && (
          <Button
            type="button"
            size="full"
            disabled={isGenerating || Boolean(previewConflict)}
            onClick={() => void handleGenerate(preview.preview_token!)}
          >
            {isGenerating ? 'Создаём план…' : 'Создать план с этими изменениями'}
          </Button>
        )}
      </CardContent>
    </Card>
  );
};

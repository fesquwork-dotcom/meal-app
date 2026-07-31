import { useId, useMemo, useState, type FC, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { Button, Input, SegmentedControl, Typography } from '@/components/ui';
import {
  computeBasketSummary,
  filterBasketItems,
  formatBasketPrice,
  formatBasketSummaryLine,
  formatCategoryMeta,
  groupBasketCategories,
  isApproximateWeight,
  presentAndFlattenBasket,
  resolveBasketEmptyState,
  type BasketPurchaseFilter,
} from '@/features/basket/basketViewModel';
import { useBasketState } from '@/features/basket/useBasketState';
import { cn } from '@/lib/utils';
import type { BasketCategory } from '@/types/basket';

export interface BasketProps {
  categories: BasketCategory[];
  totalCost: number;
  recipeCost?: number | null;
  shoppingCost?: number | null;
}

const PURCHASE_FILTERS: ReadonlyArray<{ value: BasketPurchaseFilter; label: string }> = [
  { value: 'all', label: 'Все' },
  { value: 'remaining', label: 'Не куплено' },
  { value: 'purchased', label: 'Куплено' },
];

interface BasketItemRowProps {
  id: string;
  name: string;
  weight: string;
  price: number;
  note?: string;
  primaryCaption?: string;
  checked: boolean;
  onToggle: (id: string) => void;
}

const BasketItemRow: FC<BasketItemRowProps> = ({
  id,
  name,
  weight,
  price,
  note,
  primaryCaption,
  checked,
  onToggle,
}) => {
  const approximate = isApproximateWeight(weight);

  return (
    <label
      className={cn(
        'flex min-h-11 cursor-pointer items-start gap-3 rounded-app px-1 py-2 transition-colors',
        'focus-within:ring-2 focus-within:ring-app-link focus-within:ring-offset-2 focus-within:ring-offset-app-secondary',
        checked && 'opacity-70',
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={() => onToggle(id)}
        className={cn(
          'mt-1 h-5 w-5 shrink-0 rounded border-app-hint accent-app-button',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
        )}
        aria-label={`Куплено: ${name}`}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <Typography
            variant="body"
            className={cn(
              'min-w-0 break-words leading-snug',
              checked && 'text-app-hint line-through',
            )}
          >
            {name || '—'}
          </Typography>
          <Typography
            variant="body"
            className={cn(
              'shrink-0 tabular-nums leading-snug',
              'max-[320px]:hidden',
              checked && 'text-app-hint',
            )}
          >
            {formatBasketPrice(price)}
          </Typography>
        </div>
        <Typography
          variant="body"
          className={cn(
            'mt-0.5 hidden tabular-nums leading-snug max-[320px]:block',
            checked && 'text-app-hint',
          )}
        >
          {formatBasketPrice(price)}
        </Typography>
        {weight && (
          <Typography
            variant="caption"
            className={cn(
              'mt-0.5 block leading-snug',
              approximate ? 'font-medium text-app-subtitle' : 'text-app-hint',
              checked && 'text-app-hint',
            )}
          >
            {weight}
          </Typography>
        )}
        {note && (
          <Typography variant="caption" className="mt-0.5 block text-app-hint leading-snug">
            ({note})
          </Typography>
        )}
        {primaryCaption && (
          <Typography variant="caption" className="mt-0.5 block text-app-subtitle leading-snug">
            {primaryCaption}
          </Typography>
        )}
      </div>
    </label>
  );
};

interface CategorySectionProps {
  categoryKey: string;
  label: string;
  itemCount: number;
  totalPrice: number;
  allPurchased: boolean;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  children: ReactNode;
}

const CategorySection: FC<CategorySectionProps> = ({
  categoryKey,
  label,
  itemCount,
  totalPrice,
  allPurchased,
  collapsed,
  onToggleCollapsed,
  children,
}) => {
  const baseId = useId();
  const buttonId = `${baseId}-button`;
  const contentId = `${baseId}-content`;

  return (
    <section
      className="rounded-app bg-app-secondary px-3 py-1"
      data-category={categoryKey}
      data-all-purchased={allPurchased ? 'true' : 'false'}
    >
      <button
        id={buttonId}
        type="button"
        aria-expanded={!collapsed}
        aria-controls={contentId}
        onClick={onToggleCollapsed}
        className={cn(
          'flex min-h-11 w-full items-center justify-between gap-2 py-2 text-left',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-app-link',
        )}
      >
        <span className="min-w-0 flex-1">
          <Typography variant="label" className="block truncate">
            {label}
          </Typography>
          <Typography variant="caption" className="text-app-hint">
            {formatCategoryMeta(itemCount, totalPrice)}
          </Typography>
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-app-hint transition-transform duration-200',
            !collapsed && 'rotate-180',
          )}
          aria-hidden="true"
        />
      </button>
      {!collapsed && (
        <div id={contentId} role="region" aria-labelledby={buttonId} className="pb-2">
          {children}
        </div>
      )}
    </section>
  );
};

export const Basket: FC<BasketProps> = ({
  categories,
  totalCost,
  recipeCost,
  shoppingCost,
}) => {
  const { toggleItem, markAll, clearAll, isChecked } = useBasketState();
  const [searchQuery, setSearchQuery] = useState('');
  const [purchaseFilter, setPurchaseFilter] = useState<BasketPurchaseFilter>('all');
  const [hidePurchased, setHidePurchased] = useState(false);
  const [collapsedOverrides, setCollapsedOverrides] = useState<Record<string, boolean>>({});

  const resolvedShopping =
    typeof shoppingCost === 'number' && Number.isFinite(shoppingCost)
      ? shoppingCost
      : totalCost;
  const resolvedRecipe =
    typeof recipeCost === 'number' && Number.isFinite(recipeCost) ? recipeCost : null;
  const packGap =
    resolvedRecipe !== null ? Math.max(0, resolvedShopping - resolvedRecipe) : 0;
  const showDualCost = resolvedRecipe !== null && packGap > 0.5;

  const allItems = useMemo(
    () => presentAndFlattenBasket(categories, isChecked),
    [categories, isChecked],
  );

  const summary = useMemo(
    () => computeBasketSummary(allItems, totalCost),
    [allItems, totalCost],
  );

  const visibleItems = useMemo(
    () =>
      filterBasketItems(allItems, {
        searchQuery,
        purchaseFilter,
        hidePurchased: purchaseFilter === 'all' ? hidePurchased : false,
      }),
    [allItems, searchQuery, purchaseFilter, hidePurchased],
  );

  const visibleCategories = useMemo(
    () => groupBasketCategories(visibleItems),
    [visibleItems],
  );

  const emptyState = resolveBasketEmptyState({
    totalCount: summary.totalCount,
    checkedCount: summary.checkedCount,
    visibleCount: visibleItems.length,
    searchQuery,
    purchaseFilter,
    hidePurchased: purchaseFilter === 'all' ? hidePurchased : false,
  });

  const isCategoryCollapsed = (key: string, allPurchased: boolean): boolean => {
    if (key in collapsedOverrides) {
      return collapsedOverrides[key];
    }
    return allPurchased;
  };

  const toggleCategoryCollapsed = (key: string, currentlyCollapsed: boolean) => {
    setCollapsedOverrides((prev) => ({
      ...prev,
      [key]: !currentlyCollapsed,
    }));
  };

  const handleMarkAll = () => {
    markAll(allItems.map((item) => item.id));
  };

  const emptyMessage =
    emptyState === 'search_empty'
      ? 'Продукты не найдены'
      : emptyState === 'all_purchased'
        ? 'Все продукты куплены'
        : emptyState === 'empty'
          ? 'В корзине пока нет продуктов'
          : emptyState === 'filter_empty'
            ? 'Нет продуктов в этом фильтре'
            : null;

  return (
    <div className="flex flex-col gap-3 pb-4">
      <section
        className="rounded-app bg-app-secondary px-3 py-3"
        aria-label="Сводка корзины"
        data-testid="basket-summary"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Typography variant="body" className="font-medium">
              {formatBasketSummaryLine(summary.totalCount, summary.totalCost)}
            </Typography>
            <Typography variant="caption" className="mt-0.5 text-app-hint">
              Куплено {summary.checkedCount} из {summary.totalCount}
            </Typography>
          </div>
          <Typography variant="caption" className="shrink-0 tabular-nums text-app-hint">
            {summary.progressPercent}%
          </Typography>
        </div>

        <div
          className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-app-bg"
          role="progressbar"
          aria-valuenow={summary.checkedCount}
          aria-valuemin={0}
          aria-valuemax={Math.max(summary.totalCount, 1)}
          aria-label={`Куплено ${summary.checkedCount} из ${summary.totalCount}`}
        >
          <div
            className="h-full rounded-full bg-app-button transition-[width] duration-250 ease-out motion-reduce:transition-none"
            style={{ width: `${summary.progressPercent}%` }}
          />
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={handleMarkAll}>
            Отметить всё
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={clearAll}>
            Снять отметки
          </Button>
          {purchaseFilter === 'all' && (
            <Button
              type="button"
              variant={hidePurchased ? 'secondary' : 'ghost'}
              size="sm"
              aria-pressed={hidePurchased}
              onClick={() => setHidePurchased((prev) => !prev)}
            >
              {hidePurchased ? 'Показать купленные' : 'Скрыть купленные'}
            </Button>
          )}
        </div>

        {showDualCost && resolvedRecipe !== null ? (
          <div
            className="mt-3 flex flex-col gap-1 border-t border-app-bg pt-3"
            data-testid="basket-dual-cost"
          >
            <Typography variant="caption" className="text-app-hint">
              Стоимость рецептов · {formatBasketPrice(resolvedRecipe)}
            </Typography>
            <Typography variant="caption" className="text-app-hint">
              Стоимость покупки · {formatBasketPrice(resolvedShopping)}
            </Typography>
            <Typography variant="caption" className="text-app-subtitle">
              Разница · {formatBasketPrice(packGap)}
            </Typography>
            <Typography variant="caption" className="text-app-hint">
              Причина: покупка полных упаковок
            </Typography>
          </div>
        ) : null}
      </section>

      <div className="flex flex-col gap-2">
        <Input
          type="search"
          inputSize="sm"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Поиск продукта"
          aria-label="Поиск продукта"
          autoComplete="off"
        />
        <SegmentedControl
          aria-label="Фильтр покупок"
          options={PURCHASE_FILTERS}
          value={purchaseFilter}
          onChange={setPurchaseFilter}
        />
      </div>

      {emptyMessage ? (
        <Typography
          variant="body"
          className="rounded-app bg-app-secondary px-3 py-6 text-center text-app-hint"
          role="status"
        >
          {emptyMessage}
        </Typography>
      ) : (
        <div className="flex flex-col gap-2">
          {visibleCategories.map((category) => {
            const collapsed = isCategoryCollapsed(category.key, category.allPurchased);
            return (
              <CategorySection
                key={category.key}
                categoryKey={category.key}
                label={category.label}
                itemCount={category.itemCount}
                totalPrice={category.totalPrice}
                allPurchased={category.allPurchased}
                collapsed={collapsed}
                onToggleCollapsed={() => toggleCategoryCollapsed(category.key, collapsed)}
              >
                {category.items.map((item) => (
                  <BasketItemRow
                    key={item.id}
                    id={item.id}
                    name={item.name}
                    weight={item.weight}
                    price={item.price}
                    note={item.note}
                    primaryCaption={item.primaryCaption}
                    checked={item.checked}
                    onToggle={toggleItem}
                  />
                ))}
              </CategorySection>
            );
          })}
        </div>
      )}
    </div>
  );
};

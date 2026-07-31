/** Presentation helpers for shopping basket categories, badges, and advice. */

export interface PresentedBasketItem {
  name: string;
  weight: string;
  price: number;
  note?: string;
  /** Single primary caption under quantity (Sprint 10.5.3). */
  primaryCaption?: string;
  badges: string[];
  shoppingAdvice: string[];
  usedInRecipes?: number | null;
}

export interface PresentedBasketCategory {
  category: string;
  title: string;
  items: PresentedBasketItem[];
}

const CATEGORY_ICONS: Record<string, string> = {
  мясо: '🥩',
  рыба: '🐟',
  овощи: '🥬',
  фрукты: '🍎',
  'молочные продукты': '🥛',
  молочное: '🥛',
  крупы: '🌾',
  бакалея: '🛒',
  специи: '🧂',
  соусы: '🫙',
  прочее: '🧺',
  продукты: '🧺',
};

const DISPLAY_NAME_MAP: Record<string, string> = {
  помидор: 'Помидоры',
  томат: 'Помидоры',
  томаты: 'Помидоры',
  'куриная грудка': 'Куриное филе',
  'куриное филе': 'Куриное филе',
  рис: 'Рис',
  булгур: 'Булгур',
  киноа: 'Киноа',
  нут: 'Нут',
  тахини: 'Тахини',
};

const GLOSSARY: Record<string, string> = {
  тахини: 'кунжутная паста',
  булгур: 'пшеничная крупа',
  киноа: 'зерновая культура',
  нут: 'турецкий горох',
};

function normalizeKey(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[-–—]+/g, ' ')
    .replace(/\s+/g, ' ');
}

function prettyName(name: string): string {
  const stripped = name.trim();
  if (!stripped) {
    return stripped;
  }
  return stripped[0].toUpperCase() + stripped.slice(1);
}

export function resolveBasketDisplayName(name: string): string {
  const key = normalizeKey(name);
  if (!key) {
    return '';
  }
  // Never surface snake_case / underscore canonical keys.
  if (key.includes('_') && !key.includes(' ')) {
    return prettyName(key.replace(/_/g, ' '));
  }
  if (DISPLAY_NAME_MAP[key]) {
    return DISPLAY_NAME_MAP[key];
  }
  const soft = Object.entries(DISPLAY_NAME_MAP)
    .filter(([alias]) => new RegExp(`(?<!\\w)${escapeRegExp(alias)}(?!\\w)`).test(key))
    .sort((a, b) => b[0].length - a[0].length);
  if (soft.length > 0) {
    return soft[0][1];
  }
  return prettyName(name);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function glossaryNote(name: string): string | undefined {
  const key = normalizeKey(name);
  if (GLOSSARY[key]) {
    return GLOSSARY[key];
  }
  const soft = Object.entries(GLOSSARY)
    .filter(([alias]) => key.includes(alias))
    .sort((a, b) => b[0].length - a[0].length);
  return soft[0]?.[1];
}

export function normalizeCategoryLabel(category: string): string {
  const raw = category.trim();
  if (!raw) {
    return 'Прочее';
  }
  const key = normalizeKey(raw);
  if (key === 'молочное' || key === 'молочные') {
    return 'Молочные продукты';
  }
  if (key === 'продукты' || key === 'другое' || key === 'прочее') {
    return 'Прочее';
  }
  return prettyName(raw);
}

export function formatCategoryTitle(category: string): string {
  const normalized = normalizeCategoryLabel(category);
  const icon = CATEGORY_ICONS[normalizeKey(normalized)] ?? '🧺';
  return `${icon} ${normalized}`;
}

export function guessCategory(name: string): string {
  const key = normalizeKey(name);
  const hints: Array<[string, string]> = [
    ['курин', 'Мясо'],
    ['говядин', 'Мясо'],
    ['свинин', 'Мясо'],
    ['индейк', 'Мясо'],
    ['рыб', 'Рыба'],
    ['лосос', 'Рыба'],
    ['молок', 'Молочные продукты'],
    ['сыр', 'Молочные продукты'],
    ['творог', 'Молочные продукты'],
    ['яйц', 'Молочные продукты'],
    ['помидор', 'Овощи'],
    ['томат', 'Овощи'],
    ['огурец', 'Овощи'],
    ['морков', 'Овощи'],
    ['лук', 'Овощи'],
    ['рис', 'Крупы'],
    ['греч', 'Крупы'],
    ['булгур', 'Крупы'],
    ['киноа', 'Крупы'],
    ['паприк', 'Специи'],
    ['кумин', 'Специи'],
    ['тахини', 'Соусы'],
    ['соус', 'Соусы'],
  ];
  for (const [fragment, category] of hints) {
    if (key.includes(fragment)) {
      return category;
    }
  }
  return 'Прочее';
}

function buildBadges(input: {
  usedInRecipes?: number | null;
  shoppingAdvice?: string[];
  badges?: string[];
}): string[] {
  if (input.badges && input.badges.length > 0) {
    return input.badges.slice(0, 3);
  }
  const badges: string[] = [];
  const used = input.usedInRecipes ?? 0;
  if (used >= 3) {
    badges.push(`Используется в ${used} блюдах`);
  } else if (used === 2) {
    badges.push('Есть в нескольких рецептах');
  } else if (used === 1) {
    badges.push('Покупается один раз');
  }
  const advice = input.shoppingAdvice ?? [];
  if (advice.includes('Нужно купить свежим')) {
    badges.push('Нужно купить свежим');
  } else if (advice.includes('Лучше купить охлаждённым')) {
    badges.push('Лучше купить охлаждённым');
  }
  return badges.slice(0, 3);
}

const USAGE_CAPTION = /^(Используется в |Есть в нескольких рецептах|Покупается один раз)/;

function resolvePrimaryCaption(input: {
  shoppingAdvice: string[];
  badges: string[];
  usedInRecipes?: number | null;
}): string | undefined {
  const advice = input.shoppingAdvice.find((line) => line && !USAGE_CAPTION.test(line));
  if (advice) {
    return advice;
  }

  const used = input.usedInRecipes ?? 0;
  if (used >= 3) {
    return `Используется в ${used} рецептах`;
  }
  if (used === 2) {
    return 'Есть в нескольких рецептах';
  }
  if (used === 1) {
    return 'Покупается один раз';
  }

  const badge = input.badges.find((line) => line && !USAGE_CAPTION.test(line));
  if (badge) {
    return badge;
  }

  const usageBadge = input.badges.find((line) => USAGE_CAPTION.test(line));
  if (usageBadge) {
    return usageBadge.replace(/блюдах$/, 'рецептах').replace(/блюд$/, 'рецептов');
  }

  return undefined;
}

function extraUniqueBadges(badges: string[], primaryCaption: string | undefined): string[] {
  if (!primaryCaption) {
    return [];
  }
  return badges
    .filter((badge) => badge !== primaryCaption)
    .filter((badge) => {
      // Drop usage duplicates when primary already covers usage/advice.
      if (USAGE_CAPTION.test(badge) && USAGE_CAPTION.test(primaryCaption)) {
        return false;
      }
      if (badge === primaryCaption) {
        return false;
      }
      return !primaryCaption.includes(badge) && !badge.includes(primaryCaption);
    })
    .slice(0, 1);
}

export function presentBasketCategories(
  categories: Array<{
    category: string;
    items: Array<{
      name: string;
      weight: string;
      price: number;
      used_in_recipes?: number | null;
      shopping_advice?: string[];
      badges?: string[];
    }>;
  }>,
): PresentedBasketCategory[] {
  // Preserve category/item order for stable checkbox IDs.
  return categories.map((category) => {
    const label = normalizeCategoryLabel(category.category);
    return {
      category: label,
      title: formatCategoryTitle(label),
      items: category.items.map((item) => {
        const displayName = resolveBasketDisplayName(item.name);
        const shoppingAdvice = item.shopping_advice ?? [];
        const badges = buildBadges({
          usedInRecipes: item.used_in_recipes,
          shoppingAdvice,
          badges: item.badges,
        });
        const primaryCaption = resolvePrimaryCaption({
          shoppingAdvice,
          badges,
          usedInRecipes: item.used_in_recipes,
        });
        return {
          name: displayName,
          weight: item.weight,
          price: item.price,
          note: glossaryNote(item.name) ?? glossaryNote(displayName),
          primaryCaption,
          badges: extraUniqueBadges(badges, primaryCaption),
          shoppingAdvice,
          usedInRecipes: item.used_in_recipes,
        };
      }),
    };
  });
}

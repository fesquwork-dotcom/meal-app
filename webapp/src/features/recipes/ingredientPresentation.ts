/** Presentation helpers for recipe ingredients (display names, groups, glossary). */

export type IngredientGroupId = 'main' | 'spices' | 'sauces' | 'pantry';

export interface IngredientGroup {
  id: IngredientGroupId;
  title: string;
  items: PresentedIngredient[];
}

export interface PresentedIngredient {
  name: string;
  amount: string;
  note?: string;
  pantryLabel?: string;
  contribution?: string | null;
}

const DISPLAY_NAME_MAP: Record<string, string> = {
  помидор: 'Помидоры',
  томат: 'Помидоры',
  томаты: 'Помидоры',
  огурец: 'Огурцы',
  огурцы: 'Огурцы',
  лук: 'Лук',
  'лук репчатый': 'Лук',
  морковь: 'Морковь',
  картофель: 'Картофель',
  картошка: 'Картофель',
  чеснок: 'Чеснок',
  'куриная грудка': 'Куриное филе',
  'куриное филе': 'Куриное филе',
  'филе курицы': 'Куриное филе',
  рис: 'Рис',
  гречка: 'Гречка',
  булгур: 'Булгур',
  киноа: 'Киноа',
  нут: 'Нут',
  молоко: 'Молоко',
  яйцо: 'Яйца',
  яйца: 'Яйца',
  сыр: 'Сыр',
  творог: 'Творог',
  паприка: 'Паприка',
  'чёрный перец': 'Чёрный перец',
  'черный перец': 'Чёрный перец',
  тахини: 'Тахини',
  соль: 'Соль',
};

const GLOSSARY: Record<string, string> = {
  тахини: 'кунжутная паста',
  тахин: 'кунжутная паста',
  булгур: 'пшеничная крупа',
  киноа: 'зерновая культура',
  нут: 'турецкий горох',
  мисо: 'паста из ферментированных соевых бобов',
  тофу: 'соевый творог',
  кускус: 'пшеничная крупа мелкого помола',
  'гарам масала': 'смесь индийских специй',
  харисса: 'острая перечная паста',
  харрисса: 'острая перечная паста',
  сумах: 'кислая ягодная приправа',
  суммах: 'кислая ягодная приправа',
};

const SPICE_FRAGMENTS = [
  'паприк',
  'кумин',
  'кориандр',
  'куркум',
  'орегано',
  'базилик',
  'кориц',
  'ваниль',
  'перец черн',
  'перец чёрн',
  'чёрный перец',
  'черный перец',
  'специ',
  'приправ',
  'чили',
  'карри',
  'гарам масала',
  'сумах',
  'суммах',
];

const SAUCE_FRAGMENTS = [
  'соус',
  'тахини',
  'уксус',
  'майонез',
  'горчиц',
  'кетчуп',
  'мисо',
  'харисса',
  'харрисса',
];

function normalizeKey(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[-–—]+/g, ' ')
    .replace(/\s+/g, ' ');
}

export function prettyIngredientName(name: string): string {
  const stripped = name.trim();
  if (!stripped) {
    return stripped;
  }
  return stripped[0].toUpperCase() + stripped.slice(1);
}

export function resolveDisplayName(name: string): string {
  const key = normalizeKey(name);
  if (!key) {
    return '';
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
  return prettyIngredientName(name);
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
    .filter(([alias]) => new RegExp(`(?<!\\w)${escapeRegExp(alias)}(?!\\w)`).test(key))
    .sort((a, b) => b[0].length - a[0].length);
  return soft[0]?.[1];
}

function pantryLabel(contribution?: string | null): string | undefined {
  if (contribution === 'pantry') {
    return 'Есть дома';
  }
  if (contribution === 'from_source') {
    return 'Из заготовки';
  }
  return undefined;
}

function classifyGroup(name: string, contribution?: string | null): IngredientGroupId {
  if (contribution === 'pantry') {
    return 'pantry';
  }
  const key = normalizeKey(name);
  if (SAUCE_FRAGMENTS.some((fragment) => key.includes(fragment))) {
    return 'sauces';
  }
  if (SPICE_FRAGMENTS.some((fragment) => key.includes(fragment))) {
    return 'spices';
  }
  return 'main';
}

const GROUP_TITLES: Record<IngredientGroupId, string> = {
  main: 'Основные продукты',
  spices: 'Специи',
  sauces: 'Соусы',
  pantry: 'Обычно есть дома',
};

export function presentIngredient(input: {
  name: string;
  amount: string;
  contribution?: string | null;
}): PresentedIngredient {
  const displayName = resolveDisplayName(input.name);
  return {
    name: displayName,
    amount: input.amount.trim(),
    note: glossaryNote(input.name) ?? glossaryNote(displayName),
    pantryLabel: pantryLabel(input.contribution),
    contribution: input.contribution,
  };
}

export function groupIngredients(
  ingredients: Array<{ name: string; amount: string; contribution?: string | null }>,
): IngredientGroup[] {
  const buckets: Record<IngredientGroupId, PresentedIngredient[]> = {
    main: [],
    spices: [],
    sauces: [],
    pantry: [],
  };

  for (const ingredient of ingredients) {
    const presented = presentIngredient(ingredient);
    const group = classifyGroup(ingredient.name, ingredient.contribution);
    buckets[group].push(presented);
  }

  const order: IngredientGroupId[] = ['main', 'spices', 'sauces', 'pantry'];
  const nonEmptyGroups = order
    .filter((id) => buckets[id].length > 0)
    .map((id) => ({ id, title: GROUP_TITLES[id], items: buckets[id] }));

  // If everything landed in one group, hide section titles for cleaner UI.
  if (nonEmptyGroups.length <= 1) {
    return nonEmptyGroups.map((group) => ({ ...group, title: 'Что понадобится' }));
  }

  return nonEmptyGroups;
}

export function formatCookTime(cookTime: string): string {
  const trimmed = cookTime.trim();
  if (!trimmed) {
    return '';
  }
  if (/мин|час|h|m/i.test(trimmed)) {
    return trimmed;
  }
  if (/^\d+$/.test(trimmed)) {
    return `${trimmed} минут`;
  }
  return trimmed;
}

export function formatCalories(calories?: string): string {
  if (!calories?.trim()) {
    return '';
  }
  const trimmed = calories.trim();
  if (/ккал/i.test(trimmed)) {
    return trimmed;
  }
  return `${trimmed} ккал`;
}

export function normalizeTips(raw: unknown): string[] {
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    return trimmed ? [trimmed] : [];
  }
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean);
}

export interface RecipeSubstitute {
  original: string;
  replacement: string;
}

export function normalizeSubstitutes(raw: unknown): RecipeSubstitute[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const result: RecipeSubstitute[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      continue;
    }
    const record = item as Record<string, unknown>;
    const original = record.original ?? record.from ?? record.ingredient;
    const replacement = record.replacement ?? record.to ?? record.substitute;
    if (typeof original !== 'string' || typeof replacement !== 'string') {
      continue;
    }
    const from = resolveDisplayName(original);
    const to = resolveDisplayName(replacement);
    if (from && to) {
      result.push({ original: from, replacement: to });
    }
  }
  return result;
}

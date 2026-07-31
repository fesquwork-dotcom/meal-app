import { generateMenu } from '@/api/menu';
import type { MenuPlan } from '@/types/menu';

const INVALID_MENU_RESPONSE = 'Сервер вернул некорректный план меню';

/** User-facing error when API response cannot be normalized. */
export class InvalidMenuPlanError extends Error {
  constructor(message = INVALID_MENU_RESPONSE) {
    super(message);
    this.name = 'InvalidMenuPlanError';
  }
}

export async function fetchAndNormalizeMenu(
  request: Parameters<typeof generateMenu>[0],
): Promise<MenuPlan> {
  const plan = await generateMenu(request);

  if (!plan) {
    throw new InvalidMenuPlanError();
  }

  return plan;
}

export interface BasketItem {
  name: string;
  weight: string;
  price: number;
  used_in_recipes?: number | null;
  shopping_advice?: string[];
  badges?: string[];
}

export interface BasketItemApiRecord {
  name?: string;
  weight?: string;
  price?: number;
  used_in_recipes?: number | null;
  shopping_advice?: string[] | string;
  badges?: string[] | string;
}

export interface BasketCategoryApiRecord {
  category?: string;
  items?: BasketItemApiRecord[];
}

/** Normalized shopping basket category. */
export interface BasketCategory {
  category: string;
  items: BasketItem[];
}

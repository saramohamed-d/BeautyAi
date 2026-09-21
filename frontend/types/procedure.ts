export interface Procedure {
  id: string;
  name: string;
  slug: string;
  category: string;
  description?: string | null;
  typical_price_min?: number | string | null;
  typical_price_max?: number | string | null;
  created_at: string;
  updated_at: string;
}

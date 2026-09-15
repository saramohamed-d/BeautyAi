export interface Clinic {
  id: string;
  name: string;
  description?: string | null;
  address?: string | null;
  city: string;
  country: string;
  latitude?: number | null;
  longitude?: number | null;
  phone?: string | null;
  email?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

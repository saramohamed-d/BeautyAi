export interface Availability {
  id: string;
  doctor_id: string;
  clinic_id: string;
  start_time: string;
  end_time: string;
  is_booked: boolean;
  created_at: string;
  updated_at: string;
}

export interface SlotHold {
  availability_id: string;
  held_until: string;
}

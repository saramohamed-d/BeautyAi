import { useMemo } from "react";
import { useAvailability } from "@/hooks/use-availability";
import { useClinics } from "@/hooks/use-clinics";

/**
 * Clinics where a doctor currently has bookable slots.
 *
 * Derived from availability (distinct clinic_id values) rather than a
 * dedicated "doctor's clinics" endpoint, which the API doesn't expose
 * yet. See docs/api.md.
 */
export function useDoctorClinics(doctorId: string | undefined) {
  const { data: availability, isLoading: availabilityLoading } = useAvailability({
    doctor_id: doctorId,
    available: true,
    page_size: 100,
  });
  const { data: clinicsData, isLoading: clinicsLoading } = useClinics({ page_size: 100 });

  const clinics = useMemo(() => {
    if (!availability || !clinicsData) return [];
    const ids = new Set(availability.items.map((slot) => slot.clinic_id));
    return clinicsData.items.filter((clinic) => ids.has(clinic.id));
  }, [availability, clinicsData]);

  return { clinics, isLoading: Boolean(doctorId) && (availabilityLoading || clinicsLoading) };
}

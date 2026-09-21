import { useQuery } from "@tanstack/react-query";
import { fetchAppointments, type AppointmentListParams } from "@/services/appointment-service";

export function useAppointments(params: AppointmentListParams) {
  return useQuery({
    queryKey: ["appointments", params],
    queryFn: () => fetchAppointments(params),
    enabled: Boolean(params.patient_id),
  });
}

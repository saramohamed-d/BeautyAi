import { useQuery } from "@tanstack/react-query";
import { fetchAppointment } from "@/services/appointment-service";

export function useAppointment(id: string | undefined) {
  return useQuery({
    queryKey: ["appointment", id],
    queryFn: () => fetchAppointment(id as string),
    enabled: Boolean(id),
  });
}

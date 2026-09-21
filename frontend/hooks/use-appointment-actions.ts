import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cancelAppointment, rescheduleAppointment } from "@/services/appointment-service";

function useInvalidateBookings() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["appointments"] });
    queryClient.invalidateQueries({ queryKey: ["appointment"] });
    queryClient.invalidateQueries({ queryKey: ["availability"] });
    queryClient.invalidateQueries({ queryKey: ["doctor-search"] });
  };
}

export function useCancelAppointment() {
  const invalidate = useInvalidateBookings();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) => cancelAppointment(id, reason),
    onSuccess: invalidate,
  });
}

export function useRescheduleAppointment() {
  const invalidate = useInvalidateBookings();
  return useMutation({
    mutationFn: ({ id, availabilityId }: { id: string; availabilityId: string }) =>
      rescheduleAppointment(id, availabilityId),
    onSuccess: invalidate,
  });
}

/**
 * Query options for screens where staff act on what they see.
 *
 * The app-wide default keeps data for 30 seconds (app/providers.tsx),
 * which is right for browsing doctors or articles. It's wrong for the
 * clinic dashboard: a booking that arrived a moment ago must be on the
 * screen the admin is about to confirm or cancel, so these queries always
 * refetch when their screen opens.
 */
export const LIVE = { staleTime: 0, refetchOnMount: "always" } as const;

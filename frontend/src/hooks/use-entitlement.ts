import { useQuery } from "@tanstack/react-query";

import { api, Entitlement } from "@/src/lib/api";

const FALLBACK: Entitlement = { registered: false, free_remaining: 3, wallet: 0, subscribed: false, email: null };

export function useEntitlement() {
  return useQuery<Entitlement>({
    queryKey: ["entitlement"],
    queryFn: () => api.entitlements(),
    initialData: FALLBACK,
    refetchOnWindowFocus: true,
  });
}

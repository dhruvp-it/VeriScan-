import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { useEffect } from "react";
import { LogBox } from "react-native";
import { KeyboardProvider } from "react-native-keyboard-controller";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ErrorBoundary } from "@/src/components/error-boundary";
import { TermsGate } from "@/src/components/terms-gate";
import { GUEST_KEY } from "@/src/lib/api";
import { queryClient } from "@/src/query-client";
import { storage } from "@/src/utils/storage";

LogBox.ignoreAllLogs(true);

async function ensureGuestId() {
  const existing = await storage.secureGet(GUEST_KEY, "");
  if (existing) return;
  const generated = `guest-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
  await storage.secureSet(GUEST_KEY, generated);
}

export default function RootLayout() {
  useEffect(() => { ensureGuestId(); }, []);
  return (
    <ErrorBoundary>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <KeyboardProvider>
            <Stack screenOptions={{ headerShown: false, animation: "slide_from_right" }}>
              <Stack.Screen name="index" />
              <Stack.Screen name="onboarding" />
              <Stack.Screen name="(tabs)" />
              <Stack.Screen name="product/[barcode]" />
              <Stack.Screen name="contribute/[barcode]" />
              <Stack.Screen name="plans" options={{ presentation: "modal" }} />
              <Stack.Screen name="checkout" options={{ presentation: "modal" }} />
              <Stack.Screen name="preferences" options={{ presentation: "modal" }} />
              <Stack.Screen name="legal/[doc]" />
              <Stack.Screen name="forgot-password" />
              <Stack.Screen name="watchlist" />
              <Stack.Screen name="support" />
              <Stack.Screen name="admin/index" />
              <Stack.Screen name="admin/users" />
              <Stack.Screen name="admin/support" />
              <Stack.Screen name="admin/reports" />
              <Stack.Screen name="admin/pricing" />
              <Stack.Screen name="admin/promocodes" />
              <Stack.Screen name="admin/payments" />
              <Stack.Screen name="admin/duplicates" />
              <Stack.Screen name="admin/analytics" />
              <Stack.Screen name="admin/profile" />
            </Stack>
            <TermsGate />
          </KeyboardProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </ErrorBoundary>
  );
}

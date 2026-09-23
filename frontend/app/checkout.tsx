import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";

import { api, BACKEND_URL } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function CheckoutRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { credits, tier, promo, kind, plan } = useLocalSearchParams<{
    credits?: string; tier?: string; promo?: string; kind?: string; plan?: string;
  }>();
  const creditsNum = Math.max(1, Math.min(100, parseInt(credits ?? "1", 10) || 1));
  const tierVal: "intro" | "standard" = tier === "intro" ? "intro" : "standard";
  const isSubscription = kind === "subscription";
  const planVal: "monthly" | "yearly" = plan === "yearly" ? "yearly" : "monthly";
  const promoCode = (promo ?? "").trim() || undefined;

  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "failed">("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      setStatus("loading");
      try {
        const order = isSubscription
          ? await api.razorpaySubscription(planVal, promoCode)
          : await api.razorpayOrder(creditsNum, tierVal, promoCode);
        const url = `${BACKEND_URL}/api/payments/razorpay/checkout/${order.order_id}`;
        if (Platform.OS === "web") {
          window.location.assign(url);
          return;
        }
        setCheckoutUrl(url);
      } catch (e) {
        setError((e as Error).message);
        setStatus("failed");
      }
    })();
  }, [creditsNum, tierVal, promoCode, isSubscription, planVal]);

  const onNavChange = (navState: { url: string }) => {
    const url = navState.url;
    if (url.includes("/payments/razorpay/cancelled")) {
      setStatus("failed");
      setError("Payment was cancelled.");
      setCheckoutUrl(null);
    }
  };

  const onShouldStartLoad = (request: { url: string }) => {
    const url = request.url;
    if (url.includes("/api/payments/razorpay/callback")) {
      setStatus("done");
      setCheckoutUrl(null);
      queryClient.invalidateQueries({ queryKey: ["entitlement"] });
      return false;
    }
    if (url.includes("/api/payments/razorpay/cancelled")) {
      setStatus("failed");
      setError("Payment was cancelled.");
      setCheckoutUrl(null);
      return false;
    }
    return true;
  };

  const close = async () => {
    if (status === "done") {
      await queryClient.invalidateQueries({ queryKey: ["entitlement"] });
      router.replace("/(tabs)/profile");
    } else {
      router.back();
    }
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="checkout-close" onPress={close} style={styles.backButton}>
          <Ionicons name="close" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Secure checkout</Text>
      </View>
      {status === "done" ? (
        <View style={styles.center}>
          <View style={styles.iconOk}>
            <Ionicons name="checkmark" size={42} color={colors.onSuccess} />
          </View>
          <Text style={styles.big}>Payment successful</Text>
          <Text style={styles.body}>
            {isSubscription
              ? `Your ${planVal} plan is active. Enjoy unlimited scans.`
              : `${creditsNum} credit${creditsNum > 1 ? "s are" : " is"} being added to your wallet.`}
          </Text>
          <Pressable testID="checkout-done" onPress={close} style={styles.primary}>
            <Text style={styles.primaryText}>Done</Text>
          </Pressable>
        </View>
      ) : status === "failed" ? (
        <View style={styles.center}>
          <View style={styles.iconFail}>
            <Ionicons name="close" size={42} color={colors.onError} />
          </View>
          <Text style={styles.big}>Couldn&apos;t complete</Text>
          <Text style={styles.body}>{error || "Something went wrong."}</Text>
          <Pressable testID="checkout-back" onPress={close} style={styles.primary}>
            <Text style={styles.primaryText}>Back</Text>
          </Pressable>
        </View>
      ) : checkoutUrl && Platform.OS !== "web" ? (
        <WebView
          source={{ uri: checkoutUrl }}
          onNavigationStateChange={onNavChange}
          onShouldStartLoadWithRequest={onShouldStartLoad}
          startInLoadingState
          renderLoading={() => (
            <View style={styles.webviewLoading}>
              <ActivityIndicator color={colors.brandPrimary} size="large" />
            </View>
          )}
          style={{ flex: 1 }}
        />
      ) : (
        <View style={styles.center}>
          <ActivityIndicator color={colors.brandPrimary} size="large" />
          <Text style={styles.body}>Preparing your order…</Text>
        </View>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: "800" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32, gap: 12 },
  iconOk: { width: 88, height: 88, borderRadius: 44, backgroundColor: colors.success, alignItems: "center", justifyContent: "center" },
  iconFail: { width: 88, height: 88, borderRadius: 44, backgroundColor: colors.error, alignItems: "center", justifyContent: "center" },
  big: { color: colors.onSurface, fontSize: 24, fontWeight: "800" },
  body: { color: colors.onSurfaceSecondary, fontSize: 15, lineHeight: 22, textAlign: "center" },
  primary: { minHeight: 48, borderRadius: 16, backgroundColor: colors.brandPrimary, paddingHorizontal: 22, alignItems: "center", justifyContent: "center", marginTop: 8 },
  primaryText: { color: colors.onBrandPrimary, fontWeight: "800", fontSize: 15 },
  webviewLoading: { position: "absolute", inset: 0, alignItems: "center", justifyContent: "center" } as never,
}));

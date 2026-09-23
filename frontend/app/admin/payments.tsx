import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function AdminPaymentsRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-payments"], queryFn: () => api.adminPayments(), initialData: [],
  });

  const refund = useMutation({
    mutationFn: (p: { pid: string; reason: string }) => api.adminRefund(p.pid, p.reason),
    onSuccess: (r) => {
      setStatus(`Refunded (${r.refund_id}); support ticket ${r.ticket_id} created.`);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["admin-payments"] });
    },
    onError: (e) => { setError((e as Error).message); setStatus(""); },
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-payments-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Payments</Text>
      </View>
      {status ? <Text style={styles.status}>{status}</Text> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : (data ?? []).length === 0 ? (
          <Text style={styles.muted}>No completed payments yet.</Text>
        ) : (
          data!.map((order) => (
            <View key={order.razorpay_order_id} style={styles.card} testID={`admin-payment-${order.razorpay_order_id}`}>
              <View style={styles.rowBetween}>
                <Text style={styles.amount}>₹{(order.amount_paise / 100).toFixed(2)}</Text>
                <View style={[styles.pill, order.refunded && styles.pillRefunded]}>
                  <Text style={[styles.pillText, order.refunded && styles.pillTextRefunded]}>
                    {order.refunded ? "refunded" : order.kind === "subscription" ? "subscription" : "credits"}
                  </Text>
                </View>
              </View>
              <Text style={styles.meta}>{new Date(order.created_at * 1000).toLocaleString()}</Text>
              <Text style={styles.meta}>User {order.user_id}</Text>
              <Text style={styles.meta}>
                {order.kind === "subscription" ? `Plan ${order.plan ?? "—"}` : `${order.credits ?? 0} credits${order.bonus_credits ? ` + ${order.bonus_credits} bonus` : ""}`}
                {order.promo_code ? ` · ${order.promo_code}` : ""}
              </Text>
              {order.razorpay_payment_id && !order.refunded ? (
                <View style={styles.refundRow}>
                  <TextInput
                    testID={`admin-refund-reason-${order.razorpay_order_id}`}
                    value={reasons[order.razorpay_order_id] ?? ""}
                    onChangeText={(v) => setReasons({ ...reasons, [order.razorpay_order_id]: v })}
                    placeholder="Refund reason (customer-facing)"
                    placeholderTextColor={colors.muted}
                    style={styles.reasonInput}
                  />
                  <Pressable
                    testID={`admin-refund-${order.razorpay_order_id}`}
                    onPress={() => refund.mutate({ pid: order.razorpay_payment_id!, reason: reasons[order.razorpay_order_id] ?? "Refunded by support" })}
                    style={styles.warnButton}
                  >
                    <Ionicons name="return-down-back-outline" size={17} color={colors.onWarning} />
                    <Text style={styles.warnButtonText}>Refund</Text>
                  </Pressable>
                </View>
              ) : null}
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 20, fontWeight: "800" },
  status: { color: colors.brandPrimary, paddingHorizontal: 20, paddingTop: 10, fontWeight: "700" },
  error: { color: colors.error, paddingHorizontal: 20, paddingTop: 10 },
  scroll: { padding: 20, gap: 12 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, gap: 6 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  amount: { color: colors.onSurface, fontSize: 18, fontWeight: "800" },
  pill: { backgroundColor: colors.success, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  pillText: { color: colors.onSuccess, fontSize: 10, fontWeight: "900", textTransform: "uppercase", letterSpacing: 0.6 },
  pillRefunded: { backgroundColor: colors.error },
  pillTextRefunded: { color: colors.onError },
  meta: { color: colors.muted, fontSize: 12 },
  muted: { color: colors.muted, fontSize: 13, textAlign: "center", marginTop: 30 },
  refundRow: { flexDirection: "row", gap: 8, marginTop: 8, alignItems: "center" },
  reasonInput: { flex: 1, minHeight: 40, borderRadius: 12, backgroundColor: colors.surface, paddingHorizontal: 12, color: colors.onSurface, fontSize: 13 },
  warnButton: { minHeight: 40, flexDirection: "row", gap: 4, backgroundColor: colors.warning, borderRadius: 12, alignItems: "center", justifyContent: "center", paddingHorizontal: 12 },
  warnButtonText: { color: colors.onWarning, fontSize: 13, fontWeight: "800" },
}));

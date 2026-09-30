import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useEntitlement } from "@/src/hooks/use-entitlement";
import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const DAY = 86400000;

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function daysLeft(iso: string | null): number {
  if (!iso) return 0;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 0;
  return Math.max(0, Math.ceil((d.getTime() - Date.now()) / DAY));
}

export default function AdminLaunchOfferRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: entitlement } = useEntitlement();
  const isAdmin = entitlement?.role === "admin";

  const { data, isLoading } = useQuery({
    queryKey: ["admin-launch-offer"],
    queryFn: () => api.adminLaunchOffer(),
    enabled: isAdmin,
  });

  const mutation = useMutation({
    mutationFn: (payload: { active?: boolean; eligibility_ends_at?: string; free_days?: number }) =>
      api.adminUpdateLaunchOffer(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-launch-offer"] });
      queryClient.invalidateQueries({ queryKey: ["launch-offer"] });
    },
  });

  if (!isAdmin) {
    return (
      <View style={[styles.root, { paddingTop: insets.top, justifyContent: "center", alignItems: "center", padding: 24 }]}>
        <Ionicons name="shield-outline" size={40} color={colors.brandPrimary} />
        <Text style={styles.title}>Admin only</Text>
        <Text style={styles.body}>Sign in with an admin account to manage the launch offer.</Text>
        <Pressable onPress={() => router.back()} style={styles.smallButton}>
          <Text style={styles.smallButtonText}>Back</Text>
        </Pressable>
      </View>
    );
  }

  const extendBy = (days: number) => {
    const base = data?.eligibility_ends_at ? new Date(data.eligibility_ends_at) : new Date();
    const from = Number.isNaN(base.getTime()) || base.getTime() < Date.now() ? Date.now() : base.getTime();
    mutation.mutate({ eligibility_ends_at: new Date(from + days * DAY).toISOString() });
  };

  const endNow = () => mutation.mutate({ eligibility_ends_at: new Date(Date.now() - DAY).toISOString() });

  const setFreeDays = (days: number) => {
    if (days < 1 || days > 3650) return;
    mutation.mutate({ free_days: days });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="launch-offer-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Launch offer</Text>
      </View>

      {isLoading || !data ? (
        <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={[styles.statusCard, { backgroundColor: data.live ? colors.brandPrimary : colors.surfaceSecondary }]}>
            <View style={styles.statusRow}>
              <Ionicons name={data.live ? "rocket" : "pause-circle-outline"} size={22} color={data.live ? colors.onBrandPrimary : colors.muted} />
              <Text style={[styles.statusTitle, { color: data.live ? colors.onBrandPrimary : colors.onSurface }]}>
                {data.live ? "Offer is live" : "Offer is closed"}
              </Text>
            </View>
            <Text style={[styles.statusBody, { color: data.live ? colors.onBrandPrimary : colors.muted }]}>
              {data.live
                ? `New signups get ${Math.round(data.free_days / 30)} months free · ${daysLeft(data.eligibility_ends_at)} days of eligibility left`
                : "New signups fall back to the standard 3-month trial."}
            </Text>
          </View>

          <View style={styles.section}>
            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.sectionTitle}>Offer active</Text>
                <Text style={styles.hint}>Turn the launch offer on or off instantly.</Text>
              </View>
              <Switch
                testID="launch-offer-toggle"
                value={!!data.active}
                onValueChange={(v) => mutation.mutate({ active: v })}
                trackColor={{ true: colors.brandPrimary, false: colors.border }}
                thumbColor={colors.surface}
              />
            </View>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Eligibility window</Text>
            <Text style={styles.hint}>Ends on {formatDate(data.eligibility_ends_at)} · {daysLeft(data.eligibility_ends_at)} days left</Text>
            <View style={styles.buttonRow}>
              <Pressable testID="extend-30" onPress={() => extendBy(30)} style={styles.pill} disabled={mutation.isPending}>
                <Text style={styles.pillText}>+1 month</Text>
              </Pressable>
              <Pressable testID="extend-90" onPress={() => extendBy(90)} style={styles.pill} disabled={mutation.isPending}>
                <Text style={styles.pillText}>+3 months</Text>
              </Pressable>
              <Pressable testID="extend-180" onPress={() => extendBy(180)} style={styles.pill} disabled={mutation.isPending}>
                <Text style={styles.pillText}>+6 months</Text>
              </Pressable>
            </View>
            <Pressable testID="end-now" onPress={endNow} style={styles.endButton} disabled={mutation.isPending}>
              <Ionicons name="close-circle-outline" size={16} color={colors.error} />
              <Text style={styles.endText}>End offer now</Text>
            </Pressable>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Free duration per signup</Text>
            <Text style={styles.hint}>Each new download gets this much free, unlimited use.</Text>
            <View style={styles.stepper}>
              <Pressable testID="free-minus" onPress={() => setFreeDays(data.free_days - 30)} style={styles.stepButton} disabled={mutation.isPending}>
                <Ionicons name="remove" size={20} color={colors.onSurface} />
              </Pressable>
              <View style={styles.stepValue}>
                <Text style={styles.stepNumber}>{Math.round(data.free_days / 30)}</Text>
                <Text style={styles.stepUnit}>months ({data.free_days} days)</Text>
              </View>
              <Pressable testID="free-plus" onPress={() => setFreeDays(data.free_days + 30)} style={styles.stepButton} disabled={mutation.isPending}>
                <Ionicons name="add" size={20} color={colors.onSurface} />
              </Pressable>
            </View>
            <View style={styles.presetRow}>
              <Pressable testID="free-365" onPress={() => setFreeDays(365)} style={styles.presetPill}>
                <Text style={styles.presetText}>1 year</Text>
              </Pressable>
              <Pressable testID="free-180" onPress={() => setFreeDays(180)} style={styles.presetPill}>
                <Text style={styles.presetText}>6 months</Text>
              </Pressable>
              <Pressable testID="free-90" onPress={() => setFreeDays(90)} style={styles.presetPill}>
                <Text style={styles.presetText}>3 months</Text>
              </Pressable>
            </View>
          </View>

          {mutation.isError ? <Text style={styles.error}>Couldn&apos;t save. Please try again.</Text> : null}
        </ScrollView>
      )}
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 20, fontWeight: "800" },
  body: { color: colors.onSurfaceSecondary, textAlign: "center", fontSize: 14, marginTop: 6 },
  scroll: { padding: 20, gap: 16 },
  statusCard: { borderRadius: 20, padding: 18 },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  statusTitle: { fontSize: 18, fontWeight: "800" },
  statusBody: { fontSize: 13, lineHeight: 19, marginTop: 6, opacity: 0.9 },
  section: { backgroundColor: colors.surfaceSecondary, borderRadius: 18, padding: 16, gap: 6 },
  sectionTitle: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  hint: { color: colors.muted, fontSize: 12, lineHeight: 18 },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  buttonRow: { flexDirection: "row", gap: 10, marginTop: 12 },
  pill: { flex: 1, minHeight: 44, borderRadius: 12, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  pillText: { color: colors.brandPrimary, fontWeight: "800", fontSize: 13 },
  endButton: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, minHeight: 44, marginTop: 10 },
  endText: { color: colors.error, fontWeight: "700", fontSize: 13 },
  stepper: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 12 },
  stepButton: { width: 48, height: 48, borderRadius: 14, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  stepValue: { alignItems: "center" },
  stepNumber: { color: colors.onSurface, fontSize: 30, fontWeight: "800" },
  stepUnit: { color: colors.muted, fontSize: 12, marginTop: 2 },
  presetRow: { flexDirection: "row", gap: 10, marginTop: 14 },
  presetPill: { flex: 1, minHeight: 40, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  presetText: { color: colors.onSurface, fontWeight: "700", fontSize: 13 },
  error: { color: colors.error, fontSize: 13, textAlign: "center" },
  smallButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, paddingHorizontal: 18, alignItems: "center", justifyContent: "center", marginTop: 14 },
  smallButtonText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: "800" },
}));

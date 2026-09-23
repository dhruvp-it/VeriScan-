import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, CountryPricing } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function AdminPricingRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, CountryPricing>>({});
  const [status, setStatus] = useState("");

  const { data, isLoading } = useQuery<CountryPricing[]>({
    queryKey: ["admin-pricing"], queryFn: () => api.adminPricing(), initialData: [],
  });

  useEffect(() => {
    if (data) {
      const next: Record<string, CountryPricing> = {};
      for (const item of data) next[item.country] = { ...item };
      setDrafts(next);
    }
  }, [data]);

  const save = useMutation({
    mutationFn: (item: CountryPricing) => api.adminPricingUpdate(item.country, item),
    onSuccess: () => { setStatus("Saved"); queryClient.invalidateQueries({ queryKey: ["admin-pricing"] }); },
  });

  const set = (country: string, key: keyof CountryPricing, value: string) => {
    const numeric: (keyof CountryPricing)[] = ["scan_intro", "scan_standard", "monthly", "yearly", "monthly_regular", "yearly_regular"];
    const next = { ...drafts[country] } as CountryPricing;
    if (numeric.includes(key)) (next as unknown as Record<string, number>)[key] = parseFloat(value || "0");
    else (next as unknown as Record<string, string>)[key] = value;
    setDrafts({ ...drafts, [country]: next });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-pricing-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Country pricing</Text>
      </View>
      {status ? <Text style={styles.status}>{status}</Text> : null}
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : (
          data?.map((item) => {
            const draft = drafts[item.country] ?? item;
            return (
              <View key={item.country} style={styles.card} testID={`admin-pricing-${item.country}`}>
                <View style={styles.rowBetween}>
                  <Text style={styles.country}>{item.country}</Text>
                  <Text style={styles.provider}>{draft.provider}</Text>
                </View>
                <View style={styles.grid}>
                  <Field label="Currency" value={draft.currency} onChange={(v) => set(item.country, "currency", v)} />
                  <Field label="Symbol" value={draft.symbol} onChange={(v) => set(item.country, "symbol", v)} />
                  <Field label="Scan intro" value={String(draft.scan_intro)} onChange={(v) => set(item.country, "scan_intro", v)} numeric />
                  <Field label="Scan standard" value={String(draft.scan_standard)} onChange={(v) => set(item.country, "scan_standard", v)} numeric />
                  <Field label="Monthly promo" value={String(draft.monthly)} onChange={(v) => set(item.country, "monthly", v)} numeric />
                  <Field label="Monthly rack" value={String(draft.monthly_regular)} onChange={(v) => set(item.country, "monthly_regular", v)} numeric />
                  <Field label="Yearly promo" value={String(draft.yearly)} onChange={(v) => set(item.country, "yearly", v)} numeric />
                  <Field label="Yearly rack" value={String(draft.yearly_regular)} onChange={(v) => set(item.country, "yearly_regular", v)} numeric />
                  <Field label="Provider" value={draft.provider} onChange={(v) => set(item.country, "provider", v)} />
                </View>
                <Pressable
                  testID={`admin-pricing-save-${item.country}`}
                  onPress={() => save.mutate(draft)}
                  style={styles.primary}
                >
                  <Text style={styles.primaryText}>Save</Text>
                </Pressable>
              </View>
            );
          })
        )}
      </ScrollView>
    </View>
  );
}

function Field({ label, value, onChange, numeric }: { label: string; value: string; onChange: (v: string) => void; numeric?: boolean }) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        value={value} onChangeText={onChange} keyboardType={numeric ? "decimal-pad" : "default"}
        style={styles.fieldInput} placeholderTextColor={colors.muted}
      />
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 20, fontWeight: "800" },
  status: { color: colors.brandPrimary, fontWeight: "700", paddingHorizontal: 20, paddingTop: 10 },
  scroll: { padding: 20, gap: 12 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, gap: 12 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  country: { color: colors.onSurface, fontSize: 18, fontWeight: "800" },
  provider: { color: colors.brandPrimary, fontSize: 12, fontWeight: "700", textTransform: "uppercase" },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  field: { flexBasis: "48%", flexGrow: 1 },
  fieldLabel: { color: colors.muted, fontSize: 11, fontWeight: "700", marginBottom: 4 },
  fieldInput: { height: 40, borderRadius: 10, backgroundColor: colors.surface, paddingHorizontal: 10, color: colors.onSurface, fontSize: 13 },
  primary: { minHeight: 44, borderRadius: 12, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  primaryText: { color: colors.onBrandPrimary, fontWeight: "800", fontSize: 14 },
}));

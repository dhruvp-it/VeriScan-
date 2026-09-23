import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Promocode } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const KINDS = ["percent", "flat", "free_scans"] as const;

export default function AdminPromocodesRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [kind, setKind] = useState<string>("percent");
  const [value, setValue] = useState("");
  const [maxRed, setMaxRed] = useState("100");
  const [countries, setCountries] = useState("");
  const [error, setError] = useState("");

  const { data, isLoading } = useQuery<Promocode[]>({
    queryKey: ["admin-promos"], queryFn: () => api.adminPromos(), initialData: [],
  });

  const create = useMutation({
    mutationFn: () => api.adminPromoCreate({
      code: code.toUpperCase().trim(), kind, value: parseFloat(value || "0"),
      max_redemptions: parseInt(maxRed || "100", 10),
      countries: countries.split(",").map((c) => c.trim().toUpperCase()).filter(Boolean),
      expires_at: null, active: true,
    }),
    onSuccess: () => {
      setCode(""); setValue(""); setMaxRed("100"); setCountries(""); setError("");
      queryClient.invalidateQueries({ queryKey: ["admin-promos"] });
    },
    onError: (e) => setError((e as Error).message),
  });

  const deactivate = useMutation({
    mutationFn: (c: string) => api.adminPromoDeactivate(c),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-promos"] }),
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-promos-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Promo codes</Text>
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.formCard}>
          <Text style={styles.formTitle}>Create code</Text>
          <TextInput
            testID="admin-promo-code" value={code} onChangeText={setCode} autoCapitalize="characters"
            placeholder="CODE" placeholderTextColor={colors.muted} style={styles.input}
          />
          <View style={styles.chipRow}>
            {KINDS.map((k) => (
              <Pressable key={k} onPress={() => setKind(k)} testID={`admin-promo-kind-${k}`}
                style={[styles.chip, kind === k && styles.chipOn]}>
                <Text style={[styles.chipText, kind === k && styles.chipTextOn]}>{k.replace("_", " ")}</Text>
              </Pressable>
            ))}
          </View>
          <TextInput
            testID="admin-promo-value" value={value} onChangeText={setValue} keyboardType="decimal-pad"
            placeholder={kind === "percent" ? "% off (e.g. 20)" : kind === "flat" ? "Flat discount amount" : "Free scans"}
            placeholderTextColor={colors.muted} style={styles.input}
          />
          <TextInput
            testID="admin-promo-max" value={maxRed} onChangeText={setMaxRed} keyboardType="number-pad"
            placeholder="Max redemptions" placeholderTextColor={colors.muted} style={styles.input}
          />
          <TextInput
            testID="admin-promo-countries" value={countries} onChangeText={setCountries}
            placeholder="Countries (comma separated, blank = all)"
            placeholderTextColor={colors.muted} style={styles.input}
          />
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable
            testID="admin-promo-create"
            onPress={() => create.mutate()}
            disabled={code.length < 3 || !value}
            style={[styles.primary, (code.length < 3 || !value) && styles.disabled]}
          >
            <Text style={styles.primaryText}>Create code</Text>
          </Pressable>
        </View>

        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 24 }} />
        ) : (
          data?.map((promo) => (
            <View key={promo.code} style={styles.promoCard} testID={`admin-promo-${promo.code}`}>
              <View style={styles.rowBetween}>
                <Text style={styles.code}>{promo.code}</Text>
                <View style={[styles.pill, !promo.active && styles.pillInactive]}>
                  <Text style={[styles.pillText, !promo.active && styles.pillTextInactive]}>
                    {promo.active ? "active" : "off"}
                  </Text>
                </View>
              </View>
              <Text style={styles.promoMeta}>
                {promo.kind === "percent" ? `${promo.value}% off` : promo.kind === "flat" ? `${promo.value} off` : `${promo.value} free scans`}
                {" · "}{promo.redemptions}/{promo.max_redemptions} redemptions
              </Text>
              {promo.countries.length > 0 ? (
                <Text style={styles.promoMeta}>Countries: {promo.countries.join(", ")}</Text>
              ) : null}
              {promo.active ? (
                <Pressable
                  testID={`admin-promo-deactivate-${promo.code}`}
                  onPress={() => deactivate.mutate(promo.code)}
                  style={styles.warnButton}
                >
                  <Text style={styles.warnButtonText}>Deactivate</Text>
                </Pressable>
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
  scroll: { padding: 20, gap: 12 },
  formCard: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, gap: 8 },
  formTitle: { color: colors.onSurface, fontSize: 16, fontWeight: "800" },
  input: { minHeight: 44, borderRadius: 12, backgroundColor: colors.surface, paddingHorizontal: 12, color: colors.onSurface, fontSize: 14 },
  chipRow: { flexDirection: "row", gap: 8 },
  chip: { minHeight: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.borderStrong, paddingHorizontal: 12, alignItems: "center", justifyContent: "center", flexShrink: 0 },
  chipOn: { backgroundColor: colors.brandTertiary, borderColor: colors.brandSecondary },
  chipText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: "700" },
  chipTextOn: { color: colors.onBrandTertiary },
  primary: { minHeight: 44, borderRadius: 12, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", marginTop: 4 },
  primaryText: { color: colors.onBrandPrimary, fontWeight: "800", fontSize: 14 },
  disabled: { opacity: 0.55 },
  error: { color: colors.error, fontSize: 12 },
  promoCard: { backgroundColor: colors.surface, borderRadius: 16, padding: 14, gap: 6, borderWidth: 1, borderColor: colors.divider },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  code: { color: colors.onSurface, fontSize: 17, fontWeight: "900", letterSpacing: 1 },
  pill: { backgroundColor: colors.success, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  pillInactive: { backgroundColor: colors.borderStrong },
  pillText: { color: colors.onSuccess, fontSize: 10, fontWeight: "900", textTransform: "uppercase" },
  pillTextInactive: { color: colors.onSurfaceSecondary },
  promoMeta: { color: colors.muted, fontSize: 12 },
  warnButton: { minHeight: 40, borderRadius: 12, backgroundColor: colors.warning, alignItems: "center", justifyContent: "center", paddingHorizontal: 14, alignSelf: "flex-start", marginTop: 6 },
  warnButtonText: { color: colors.onWarning, fontSize: 13, fontWeight: "800" },
}));

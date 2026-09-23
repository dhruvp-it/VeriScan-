import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function AdminDuplicatesRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-duplicates"], queryFn: () => api.adminDuplicates(), initialData: [],
  });

  const merge = useMutation({
    mutationFn: (p: { primary: string; dupes: string[] }) => api.adminMerge(p.primary, p.dupes),
    onSuccess: (r) => {
      setStatus(`Merged ${r.merged} duplicate${r.merged === 1 ? "" : "s"} into ${r.primary_barcode}.`);
      queryClient.invalidateQueries({ queryKey: ["admin-duplicates"] });
    },
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-duplicates-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Duplicate products</Text>
      </View>
      {status ? <Text style={styles.status}>{status}</Text> : null}
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : (data ?? []).length === 0 ? (
          <Text style={styles.muted}>No duplicate groups detected right now.</Text>
        ) : (
          data!.map((group, idx) => {
            const key = `${group._id.name}-${group._id.brand}-${idx}`;
            const chosen = selected[key];
            return (
              <View key={key} style={styles.card} testID={`dupe-group-${idx}`}>
                <Text style={styles.groupTitle}>{group._id.name} — {group._id.brand}</Text>
                <Text style={styles.muted}>{group.count} records</Text>
                {group.products.map((p) => (
                  <Pressable
                    key={p.barcode}
                    onPress={() => setSelected({ ...selected, [key]: p.barcode })}
                    testID={`dupe-choice-${p.barcode}`}
                    style={[styles.choice, chosen === p.barcode && styles.choiceOn]}
                  >
                    <Ionicons
                      name={chosen === p.barcode ? "radio-button-on" : "radio-button-off"}
                      size={18} color={chosen === p.barcode ? colors.brandPrimary : colors.muted}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.rowText}>{p.barcode}</Text>
                      <Text style={styles.muted}>{p.category}</Text>
                    </View>
                  </Pressable>
                ))}
                <Pressable
                  testID={`dupe-merge-${idx}`}
                  disabled={!chosen}
                  onPress={() => chosen && merge.mutate({
                    primary: chosen,
                    dupes: group.products.filter((p) => p.barcode !== chosen).map((p) => p.barcode),
                  })}
                  style={[styles.primary, !chosen && styles.disabled]}
                >
                  <Text style={styles.primaryText}>Merge into selected</Text>
                </Pressable>
              </View>
            );
          })
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
  scroll: { padding: 20, gap: 12 },
  muted: { color: colors.muted, fontSize: 13, textAlign: "center", marginTop: 6 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, gap: 6 },
  groupTitle: { color: colors.onSurface, fontSize: 15, fontWeight: "800" },
  choice: { flexDirection: "row", alignItems: "center", gap: 10, padding: 10, borderRadius: 10, backgroundColor: colors.surface, marginTop: 8 },
  choiceOn: { borderWidth: 1, borderColor: colors.brandPrimary },
  rowText: { color: colors.onSurface, fontSize: 13, fontWeight: "700" },
  primary: { minHeight: 44, borderRadius: 12, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", marginTop: 10 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
  disabled: { opacity: 0.55 },
}));

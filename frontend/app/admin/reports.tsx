import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Report } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const STATUS_FILTERS = ["open", "in_progress", "resolved", "closed"] as const;

export default function AdminReportsRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<string>("open");
  const [notes, setNotes] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery<Report[]>({
    queryKey: ["admin-reports", filter],
    queryFn: () => api.adminReports(filter),
    initialData: [],
  });

  const update = useMutation({
    mutationFn: (p: { id: string; status: string; note: string }) => api.adminReportUpdate(p.id, p.status, p.note),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-reports"] }),
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-reports-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Data reports</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
        {STATUS_FILTERS.map((s) => (
          <Pressable key={s} onPress={() => setFilter(s)} testID={`admin-reports-filter-${s}`}
            style={[styles.chip, filter === s && styles.chipOn]}>
            <Text style={[styles.chipText, filter === s && styles.chipTextOn]}>{s}</Text>
          </Pressable>
        ))}
      </ScrollView>
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : (
          data?.map((report) => (
            <View key={report.id} style={styles.card} testID={`admin-report-${report.id}`}>
              <View style={styles.rowBetween}>
                <Text style={styles.subject}>Barcode {report.barcode}</Text>
                <Text style={styles.meta}>{new Date(report.created_at).toLocaleString()}</Text>
              </View>
              <Text style={styles.body}>{report.reason}</Text>
              <TextInput
                testID={`admin-report-note-${report.id}`}
                value={notes[report.id] ?? report.admin_note ?? ""}
                onChangeText={(v) => setNotes({ ...notes, [report.id]: v })}
                placeholder="Resolution note"
                placeholderTextColor={colors.muted}
                style={styles.input} multiline
              />
              <View style={styles.actions}>
                {(["in_progress", "resolved", "closed"] as const).map((next) => (
                  <Pressable
                    key={next} testID={`admin-report-${report.id}-set-${next}`}
                    onPress={() => update.mutate({ id: report.id, status: next, note: notes[report.id] ?? report.admin_note ?? "" })}
                    style={styles.button}
                  >
                    <Text style={styles.buttonText}>{next.replace("_", " ")}</Text>
                  </Pressable>
                ))}
              </View>
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
  filterRow: { paddingHorizontal: 20, paddingVertical: 14, gap: 8 },
  chip: { minHeight: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.borderStrong, paddingHorizontal: 12, alignItems: "center", justifyContent: "center", flexShrink: 0 },
  chipOn: { backgroundColor: colors.brandTertiary, borderColor: colors.brandSecondary },
  chipText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: "700" },
  chipTextOn: { color: colors.onBrandTertiary },
  scroll: { padding: 20, gap: 12 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, gap: 8 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  subject: { color: colors.onSurface, fontSize: 15, fontWeight: "800" },
  meta: { color: colors.muted, fontSize: 12 },
  body: { color: colors.onSurfaceSecondary, fontSize: 13, lineHeight: 20 },
  input: { minHeight: 60, borderRadius: 12, backgroundColor: colors.surface, padding: 12, color: colors.onSurface, fontSize: 13, textAlignVertical: "top" },
  actions: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  button: { minHeight: 38, backgroundColor: colors.brandPrimary, borderRadius: 12, paddingHorizontal: 12, alignItems: "center", justifyContent: "center" },
  buttonText: { color: colors.onBrandPrimary, fontSize: 12, fontWeight: "800", textTransform: "capitalize" },
}));

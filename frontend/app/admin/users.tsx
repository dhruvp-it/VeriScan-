import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AdminUser, api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function AdminUsersRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [reasonForUser, setReasonForUser] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");

  const { data, isLoading } = useQuery<AdminUser[]>({
    queryKey: ["admin-users", search],
    queryFn: () => api.adminUsers(search || undefined),
    initialData: [],
  });

  const suspend = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.adminSuspend(id, reason),
    onSuccess: () => { setStatus("Account suspended."); queryClient.invalidateQueries({ queryKey: ["admin-users"] }); },
  });
  const reactivate = useMutation({
    mutationFn: (id: string) => api.adminReactivate(id),
    onSuccess: () => { setStatus("Account reactivated."); queryClient.invalidateQueries({ queryKey: ["admin-users"] }); },
  });
  const sendReset = useMutation({
    mutationFn: (id: string) => api.adminSendReset(id),
    onSuccess: () => setStatus("Reset code sent."),
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-users-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Users</Text>
      </View>
      <View style={styles.searchWrap}>
        <TextInput
          testID="admin-users-search" value={search} onChangeText={setSearch}
          autoCapitalize="none" placeholder="Search email"
          placeholderTextColor={colors.muted} style={styles.searchInput}
        />
      </View>
      {status ? <Text style={styles.status}>{status}</Text> : null}
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLoading ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : (
          data?.map((user) => (
            <View key={user.id} style={styles.userCard} testID={`admin-user-${user.id}`}>
              <View style={styles.userTopRow}>
                <Text style={styles.email}>{user.email_masked}</Text>
                <View style={[styles.statusPill, user.suspended && styles.statusPillSuspended]}>
                  <Text style={[styles.statusText, user.suspended && styles.statusTextSuspended]}>
                    {user.suspended ? "suspended" : "active"}
                  </Text>
                </View>
              </View>
              <Text style={styles.meta}>Joined {new Date(user.created_at).toLocaleDateString()}</Text>
              {user.suspended ? (
                <Pressable
                  testID={`admin-reactivate-${user.id}`} onPress={() => reactivate.mutate(user.id)}
                  style={styles.primaryOutline}
                >
                  <Ionicons name="checkmark-circle-outline" size={17} color={colors.brandPrimary} />
                  <Text style={styles.primaryOutlineText}>Reactivate</Text>
                </Pressable>
              ) : (
                <View style={styles.suspendRow}>
                  <TextInput
                    value={reasonForUser[user.id] ?? ""}
                    onChangeText={(v) => setReasonForUser({ ...reasonForUser, [user.id]: v })}
                    placeholder="Reason (required)" placeholderTextColor={colors.muted}
                    style={styles.reasonInput}
                    testID={`admin-suspend-reason-${user.id}`}
                  />
                  <Pressable
                    testID={`admin-suspend-${user.id}`}
                    onPress={() => suspend.mutate({ id: user.id, reason: reasonForUser[user.id] ?? "policy violation" })}
                    style={styles.warnButton}
                  >
                    <Ionicons name="pause-circle-outline" size={17} color={colors.onWarning} />
                    <Text style={styles.warnButtonText}>Suspend</Text>
                  </Pressable>
                </View>
              )}
              <Pressable
                testID={`admin-send-reset-${user.id}`}
                onPress={() => sendReset.mutate(user.id)}
                style={styles.secondaryButton}
              >
                <Ionicons name="mail-outline" size={17} color={colors.brandPrimary} />
                <Text style={styles.secondaryButtonText}>Send reset code</Text>
              </Pressable>
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
  searchWrap: { paddingHorizontal: 20, paddingTop: 14 },
  searchInput: { height: 46, borderRadius: 14, backgroundColor: colors.surfaceTertiary, paddingHorizontal: 14, color: colors.onSurface, fontSize: 15 },
  status: { color: colors.brandPrimary, fontWeight: "700", paddingHorizontal: 20, paddingTop: 10 },
  scroll: { padding: 20, gap: 12 },
  userCard: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, gap: 8 },
  userTopRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  email: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  meta: { color: colors.muted, fontSize: 12 },
  statusPill: { backgroundColor: colors.success, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  statusPillSuspended: { backgroundColor: colors.error },
  statusText: { color: colors.onSuccess, fontSize: 10, fontWeight: "900", textTransform: "uppercase", letterSpacing: 0.6 },
  statusTextSuspended: { color: colors.onError },
  suspendRow: { flexDirection: "row", gap: 8, alignItems: "center", marginTop: 4 },
  reasonInput: { flex: 1, height: 40, borderRadius: 12, backgroundColor: colors.surface, paddingHorizontal: 12, color: colors.onSurface, fontSize: 13 },
  warnButton: { minHeight: 40, flexDirection: "row", gap: 4, backgroundColor: colors.warning, borderRadius: 12, alignItems: "center", justifyContent: "center", paddingHorizontal: 12 },
  warnButtonText: { color: colors.onWarning, fontSize: 13, fontWeight: "800" },
  primaryOutline: { minHeight: 40, flexDirection: "row", gap: 6, borderRadius: 12, borderWidth: 1, borderColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 12 },
  primaryOutlineText: { color: colors.brandPrimary, fontWeight: "800", fontSize: 13 },
  secondaryButton: { minHeight: 40, flexDirection: "row", gap: 6, backgroundColor: colors.surface, borderRadius: 12, alignItems: "center", justifyContent: "center", paddingHorizontal: 12 },
  secondaryButtonText: { color: colors.brandPrimary, fontWeight: "800", fontSize: 13 },
}));

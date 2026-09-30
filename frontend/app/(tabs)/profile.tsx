import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AuthModal } from "@/src/components/auth-modal";
import { useEntitlement } from "@/src/hooks/use-entitlement";
import { api, TOKEN_KEY } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function ProfileTab() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: entitlement } = useEntitlement();
  const [authOpen, setAuthOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const signOut = async () => {
    await storage.secureRemove(TOKEN_KEY);
    await queryClient.invalidateQueries();
  };

  const confirmDelete = () => {
    Alert.alert(
      "Delete account?",
      "This permanently deletes your account, scan history, watchlist and preferences. This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              setDeleting(true);
              await api.deleteAccount();
              await storage.secureRemove(TOKEN_KEY);
              await queryClient.invalidateQueries();
              router.replace("/");
            } catch {
              Alert.alert("Couldn't delete account", "Please try again in a moment.");
            } finally {
              setDeleting(false);
            }
          },
        },
      ],
    );
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.eyebrow}>YOUR VERISCAN</Text>
            <Text style={styles.title}>Profile & plans</Text>
          </View>
          <View style={styles.avatar}>
            <Ionicons name="person" size={20} color={colors.onBrandPrimary} />
          </View>
        </View>

        <View style={styles.profileCard} testID="profile-card">
          <Text style={styles.label}>
            {entitlement?.registered ? "SIGNED IN AS" : "GUEST MODE"}
          </Text>
          <Text style={styles.email}>
            {entitlement?.email ?? "Your preferences are saved on this device"}
          </Text>
          <Text style={styles.body}>
            {entitlement?.registered
              ? "Your monthly quota and scan history are synced."
              : "Create an account after your three free scans to keep your history."}
          </Text>
          {!entitlement?.registered && (
            <Pressable testID="profile-sign-in" onPress={() => setAuthOpen(true)} style={styles.primaryButton}>
              <Text style={styles.primaryText}>Create free account</Text>
              <Ionicons name="arrow-forward" size={18} color={colors.onBrandPrimary} />
            </Pressable>
          )}
        </View>

        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.cardTitle}>Scan wallet</Text>
            <Text style={styles.wallet}>
              {entitlement?.subscribed ? "Unlimited" : `${entitlement?.wallet ?? 0} credits`}
            </Text>
          </View>
          <Text style={styles.body}>
            {entitlement?.subscribed
              ? "Your launch subscription is active."
              : `${entitlement?.free_remaining ?? 0} complimentary scans remain this period.`}
          </Text>
          <Pressable testID="profile-plans" onPress={() => router.push("/plans")} style={styles.outlineButton}>
            <Ionicons name="sparkles-outline" size={19} color={colors.brandPrimary} />
            <Text style={styles.outlineText}>View launch plans</Text>
          </Pressable>
        </View>

        <Pressable testID="profile-edit-preferences" onPress={() => router.push("/preferences")} style={styles.rowLink}>
          <Ionicons name="options-outline" size={20} color={colors.brandPrimary} />
          <Text style={styles.rowLinkText}>Edit clean profile</Text>
          <Ionicons name="chevron-forward" size={17} color={colors.muted} />
        </Pressable>

        {entitlement?.registered ? (
          <Pressable testID="profile-watchlist" onPress={() => router.push("/watchlist")} style={styles.rowLink}>
            <Ionicons name="heart-outline" size={20} color={colors.brandPrimary} />
            <Text style={styles.rowLinkText}>Watchlist</Text>
            <Ionicons name="chevron-forward" size={17} color={colors.muted} />
          </Pressable>
        ) : null}

        <Pressable testID="profile-support" onPress={() => router.push("/support")} style={styles.rowLink}>
          <Ionicons name="chatbubble-ellipses-outline" size={20} color={colors.brandPrimary} />
          <Text style={styles.rowLinkText}>Support</Text>
          <Ionicons name="chevron-forward" size={17} color={colors.muted} />
        </Pressable>

        <Pressable testID="profile-terms" onPress={() => router.push({ pathname: "/legal/[doc]", params: { doc: "terms" } })} style={styles.rowLink}>
          <Ionicons name="document-text-outline" size={20} color={colors.brandPrimary} />
          <Text style={styles.rowLinkText}>Terms of Service</Text>
          <Ionicons name="chevron-forward" size={17} color={colors.muted} />
        </Pressable>

        <Pressable testID="profile-privacy" onPress={() => router.push({ pathname: "/legal/[doc]", params: { doc: "privacy" } })} style={styles.rowLink}>
          <Ionicons name="shield-outline" size={20} color={colors.brandPrimary} />
          <Text style={styles.rowLinkText}>Privacy Policy</Text>
          <Ionicons name="chevron-forward" size={17} color={colors.muted} />
        </Pressable>

        {entitlement?.role === "admin" ? (
          <Pressable testID="profile-admin" onPress={() => router.push("/admin")} style={styles.rowLink}>
            <Ionicons name="shield-checkmark-outline" size={20} color={colors.brandSecondary} />
            <Text style={[styles.rowLinkText, { color: colors.brandSecondary }]}>Admin dashboard</Text>
            <Ionicons name="chevron-forward" size={17} color={colors.muted} />
          </Pressable>
        ) : null}

        {entitlement?.registered && (
          <Pressable testID="profile-sign-out" onPress={signOut} style={styles.rowLink}>
            <Ionicons name="log-out-outline" size={20} color={colors.error} />
            <Text style={[styles.rowLinkText, { color: colors.error }]}>Sign out</Text>
            <Ionicons name="chevron-forward" size={17} color={colors.muted} />
          </Pressable>
        )}

        {entitlement?.registered && (
          <Pressable testID="profile-delete-account" onPress={confirmDelete} disabled={deleting} style={styles.rowLink}>
            <Ionicons name="trash-outline" size={20} color={colors.error} />
            <Text style={[styles.rowLinkText, { color: colors.error }]}>
              {deleting ? "Deleting…" : "Delete account"}
            </Text>
            <Ionicons name="chevron-forward" size={17} color={colors.muted} />
          </Pressable>
        )}
      </ScrollView>
      <AuthModal visible={authOpen} onClose={() => setAuthOpen(false)} />
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 32 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 22 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 27, fontWeight: "800", marginTop: 8 },
  avatar: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  profileCard: { backgroundColor: colors.brandTertiary, borderRadius: 22, padding: 20, marginBottom: 16 },
  label: { color: colors.muted, fontSize: 11, fontWeight: "800", letterSpacing: 0.8 },
  email: { color: colors.onBrandTertiary, fontSize: 19, fontWeight: "800", marginTop: 8, marginBottom: 8 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21 },
  primaryButton: { minHeight: 48, borderRadius: 16, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8, marginTop: 16 },
  primaryText: { color: colors.onBrandPrimary, fontWeight: "800", fontSize: 15 },
  card: { borderRadius: 20, backgroundColor: colors.surfaceSecondary, padding: 18, marginBottom: 16 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  cardTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  wallet: { color: colors.brandPrimary, fontSize: 15, fontWeight: "800" },
  outlineButton: { minHeight: 48, borderRadius: 16, borderWidth: 1, borderColor: colors.brandPrimary, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginTop: 14 },
  outlineText: { color: colors.brandPrimary, fontSize: 14, fontWeight: "800" },
  rowLink: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 56, paddingHorizontal: 4 },
  rowLinkText: { flex: 1, color: colors.onSurface, fontSize: 15, fontWeight: "700" },
}));

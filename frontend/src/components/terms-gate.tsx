import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export function TermsGate() {
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["terms-status"],
    queryFn: () => api.termsStatus(),
    refetchOnWindowFocus: false,
  });
  const accept = useMutation({
    mutationFn: () => api.acceptTerms(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["terms-status"] });
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  const visible = !!data?.registered && !data.up_to_date;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={() => {}}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <Text style={styles.eyebrow}>ACTION REQUIRED</Text>
          <Text style={styles.title}>Our Terms & Privacy Policy have been updated</Text>
          <Text style={styles.body}>
            We've published new Terms of Service and Privacy Policy (v{data?.terms_version}). Before you continue using VeriScan or make any purchase, please review and accept them.
          </Text>
          <View style={styles.bulletBox}>
            <View style={styles.bulletRow}>
              <Ionicons name="alert-circle" size={16} color={colors.warning ?? colors.brandSecondary} />
              <Text style={styles.bulletText}>All subscription purchases are <Text style={styles.bold}>non-refundable and non-cancellable</Text> once activated.</Text>
            </View>
            <View style={styles.bulletRow}>
              <Ionicons name="alert-circle" size={16} color={colors.warning ?? colors.brandSecondary} />
              <Text style={styles.bulletText}>VeriScan outputs are informational — <Text style={styles.bold}>not medical or dietary advice</Text>.</Text>
            </View>
            <View style={styles.bulletRow}>
              <Ionicons name="alert-circle" size={16} color={colors.warning ?? colors.brandSecondary} />
              <Text style={styles.bulletText}>Service is <Text style={styles.bold}>"as is"</Text>; outages, technical disruption or delayed support tickets do not create any refund right.</Text>
            </View>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.linkRow}>
            <Pressable testID="terms-gate-view-terms" onPress={() => router.push({ pathname: "/legal/[doc]", params: { doc: "terms" } })} style={styles.linkPill}>
              <Ionicons name="document-text-outline" size={15} color={colors.brandPrimary} />
              <Text style={styles.linkText}>Read Terms</Text>
            </Pressable>
            <Pressable testID="terms-gate-view-privacy" onPress={() => router.push({ pathname: "/legal/[doc]", params: { doc: "privacy" } })} style={styles.linkPill}>
              <Ionicons name="shield-outline" size={15} color={colors.brandPrimary} />
              <Text style={styles.linkText}>Read Privacy</Text>
            </Pressable>
          </ScrollView>
          <Pressable
            testID="terms-gate-accept"
            onPress={() => accept.mutate()}
            disabled={accept.isPending}
            style={[styles.primary, accept.isPending && styles.disabled]}
          >
            {accept.isPending ? <ActivityIndicator color={colors.onBrandPrimary} /> : (
              <Text style={styles.primaryText}>I have read and accept both</Text>
            )}
          </Pressable>
          {accept.isError ? <Text style={styles.error}>{(accept.error as Error).message}</Text> : null}
        </View>
      </View>
    </Modal>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(15,17,15,0.55)", justifyContent: "flex-end" },
  sheet: { backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 22, paddingBottom: 34 },
  handle: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: colors.borderStrong, marginBottom: 16 },
  eyebrow: { color: colors.brandSecondary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 22, fontWeight: "800", marginTop: 8, lineHeight: 28 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21, marginTop: 10 },
  bulletBox: { marginTop: 14, gap: 10, backgroundColor: colors.surfaceSecondary, padding: 14, borderRadius: 16 },
  bulletRow: { flexDirection: "row", gap: 8, alignItems: "flex-start" },
  bulletText: { flex: 1, color: colors.onSurfaceSecondary, fontSize: 13, lineHeight: 19 },
  bold: { fontWeight: "800", color: colors.onSurface },
  linkRow: { gap: 10, marginTop: 14 },
  linkPill: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.surfaceSecondary, borderRadius: 14, paddingHorizontal: 12, paddingVertical: 8 },
  linkText: { color: colors.brandPrimary, fontSize: 13, fontWeight: "700" },
  primary: { minHeight: 52, borderRadius: 18, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10, marginTop: 16 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 15, fontWeight: "800" },
  disabled: { opacity: 0.6 },
  error: { color: colors.error, fontSize: 13, marginTop: 10, textAlign: "center" },
}));

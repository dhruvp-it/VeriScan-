import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

const SEEN_KEY = "veriscan_launch_welcome_seen";

function monthsFromDays(days: number): string {
  if (days % 365 === 0 && days >= 365) {
    const y = days / 365;
    return `${y} year${y > 1 ? "s" : ""}`;
  }
  if (days % 30 === 0) {
    const m = days / 30;
    return `${m} month${m > 1 ? "s" : ""}`;
  }
  return `${days} days`;
}

function formatDeadline(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

export function LaunchWelcome() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [checked, setChecked] = useState(false);
  const [visible, setVisible] = useState(false);

  const { data: offer } = useQuery({
    queryKey: ["launch-offer"],
    queryFn: () => api.launchOffer(),
    staleTime: 1000 * 60 * 60,
  });

  useEffect(() => {
    (async () => {
      const seen = await storage.getItem(SEEN_KEY, false);
      setVisible(!seen);
      setChecked(true);
    })();
  }, []);

  const dismiss = async () => {
    await storage.setItem(SEEN_KEY, true);
    setVisible(false);
  };

  if (!checked || !visible) return null;

  const freeLabel = offer ? monthsFromDays(offer.free_days) : "1 year";
  const deadline = formatDeadline(offer?.eligibility_ends_at ?? null);
  const isLive = offer?.active ?? true;

  const perks = [
    { icon: "infinite" as const, title: "Unlimited scans", body: `Scan as much as you like — free for ${freeLabel}.` },
    { icon: "card-outline" as const, title: "No payment needed", body: "No card, no subscription. Just download and go." },
    { icon: "sparkles-outline" as const, title: "Every feature unlocked", body: "Health scores, dietary match, badges, alternatives & more." },
  ];

  return (
    <View style={[styles.backdrop, { paddingTop: insets.top }]} testID="launch-welcome">
      <View style={styles.card}>
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
          <View style={styles.badge}>
            <Ionicons name="rocket" size={14} color={colors.onBrandPrimary} />
            <Text style={styles.badgeText}>WE'RE LIVE</Text>
          </View>

          <View style={styles.hero}>
            <Ionicons name="gift" size={34} color={colors.onBrandPrimary} />
          </View>

          <Text style={styles.title}>
            {isLive ? `Welcome — enjoy ${freeLabel} free!` : "Welcome to VeriScan"}
          </Text>
          <Text style={styles.subtitle}>
            {isLive
              ? `To celebrate our launch, every download gets a full ${freeLabel} of VeriScan free with unlimited scans. No payment method required.`
              : "Scan any product for an instant ingredient health score, dietary match, and cleaner alternatives."}
          </Text>

          <View style={styles.perks}>
            {perks.map((p) => (
              <View key={p.title} style={styles.perkRow}>
                <View style={styles.perkIcon}>
                  <Ionicons name={p.icon} size={18} color={colors.brandPrimary} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.perkTitle}>{p.title}</Text>
                  <Text style={styles.perkBody}>{p.body}</Text>
                </View>
              </View>
            ))}
          </View>

          {isLive && deadline ? (
            <View style={styles.notice}>
              <Ionicons name="time-outline" size={15} color={colors.brandPrimary} />
              <Text style={styles.noticeText}>Launch offer — sign up before {deadline}.</Text>
            </View>
          ) : null}

          <Pressable testID="launch-welcome-cta" onPress={dismiss} style={styles.cta}>
            <Text style={styles.ctaText}>Start scanning</Text>
            <Ionicons name="arrow-forward" size={18} color={colors.onBrandPrimary} />
          </Pressable>
        </ScrollView>
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: colors.surface, zIndex: 60, justifyContent: "center" },
  card: { flex: 1, justifyContent: "center" },
  scroll: { padding: 24, paddingBottom: 40, alignItems: "center" },
  badge: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.brandPrimary, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, marginBottom: 24 },
  badgeText: { color: colors.onBrandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.2 },
  hero: { width: 92, height: 92, borderRadius: 28, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", marginBottom: 24 },
  title: { color: colors.onSurface, fontSize: 27, fontWeight: "800", textAlign: "center" },
  subtitle: { color: colors.onSurfaceSecondary, fontSize: 15, lineHeight: 23, textAlign: "center", marginTop: 12, marginBottom: 28 },
  perks: { width: "100%", gap: 16 },
  perkRow: { flexDirection: "row", alignItems: "flex-start", gap: 14 },
  perkIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  perkTitle: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  perkBody: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 2 },
  notice: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: colors.surfaceSecondary, borderRadius: 14, padding: 14, marginTop: 26, width: "100%" },
  noticeText: { color: colors.onSurfaceSecondary, fontSize: 13, fontWeight: "600", flex: 1 },
  cta: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10, backgroundColor: colors.brandPrimary, minHeight: 54, borderRadius: 18, marginTop: 28, width: "100%" },
  ctaText: { color: colors.onBrandPrimary, fontSize: 16, fontWeight: "800" },
}));

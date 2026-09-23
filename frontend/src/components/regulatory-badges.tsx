import { Ionicons } from "@expo/vector-icons";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { Badge } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  fssai: "shield-checkmark",
  fda: "medkit",
  usda_organic: "leaf",
  eu_bio: "leaf",
  peta: "heart",
  leaping_bunny: "paw",
  vegan_society: "leaf",
  trustified: "ribbon",
  informed_sport: "barbell",
  green_dot: "ellipse",
  brown_triangle: "triangle",
  gluten_free: "restaurant",
  non_gmo: "flask",
  kosher: "star",
  halal: "star",
};

export function RegulatoryBadges({ badges }: { badges: Badge[] | undefined }) {
  const styles = useStyles();
  const { colors } = useTheme();
  if (!badges || badges.length === 0) return null;
  return (
    <View style={styles.wrap} testID="regulatory-badges">
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
        {badges.map((badge) => {
          const isGreenDot = badge.id === "green_dot";
          const isBrown = badge.id === "brown_triangle";
          const dotColor = isGreenDot ? colors.success : isBrown ? colors.warning : colors.brandPrimary;
          return (
            <View key={badge.id} style={styles.chip} testID={`badge-${badge.id}`}>
              <Ionicons name={ICONS[badge.id] ?? "checkmark-circle"} size={13} color={dotColor} />
              <Text style={styles.label}>{badge.label}</Text>
              {badge.region && badge.region !== "GLOBAL" ? (
                <Text style={styles.region}>{badge.region}</Text>
              ) : null}
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  wrap: { marginTop: 12, marginBottom: 4 },
  row: { gap: 8, paddingRight: 4 },
  chip: { minHeight: 36, borderRadius: 18, backgroundColor: colors.surfaceSecondary, paddingHorizontal: 12, flexDirection: "row", alignItems: "center", gap: 6, flexShrink: 0 },
  label: { color: colors.onSurface, fontSize: 12, fontWeight: "700" },
  region: { color: colors.brandPrimary, fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
}));

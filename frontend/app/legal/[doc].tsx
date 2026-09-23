import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function LegalRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { doc } = useLocalSearchParams<{ doc: "terms" | "privacy" }>();
  const isPrivacy = doc === "privacy";
  const { data, isLoading } = useQuery({
    queryKey: ["legal", doc],
    queryFn: () => isPrivacy ? api.privacy() : api.terms(),
  });

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="legal-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>{isPrivacy ? "Privacy Policy" : "Terms of Service"}</Text>
      </View>
      <ScrollView contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + 32 }]}>
        {isLoading || !data
          ? <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
          : (
            <>
              <Text style={styles.meta} testID="legal-version">Version {data.version} · Effective {data.effective}</Text>
              <Text style={styles.body} selectable testID="legal-content">{data.content}</Text>
            </>
          )}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: "800" },
  scroll: { paddingHorizontal: 20, paddingTop: 16 },
  meta: { color: colors.muted, fontSize: 12, fontWeight: "700", marginBottom: 12 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 22 },
}));

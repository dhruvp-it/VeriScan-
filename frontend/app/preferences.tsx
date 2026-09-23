import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { PreferenceGroup } from "@/src/components/preference-group";
import { api } from "@/src/lib/api";
import {
  DIETARY_OPTIONS, emptyPreferences, Preferences,
  SENSITIVITY_OPTIONS, TARGET_OPTIONS,
} from "@/src/lib/preferences";
import { makeStyles, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function PreferencesRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [preferences, setPreferences] = useState<Preferences>(emptyPreferences);
  const [saving, setSaving] = useState(false);

  const { data } = useQuery({
    queryKey: ["profile"],
    queryFn: () => api.profile(),
  });

  useEffect(() => {
    if (data?.preferences) setPreferences(data.preferences);
  }, [data]);

  const toggle = (group: keyof Preferences, value: string) => {
    const current = preferences[group];
    setPreferences({
      ...preferences,
      [group]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value],
    });
  };

  const save = async () => {
    setSaving(true);
    await storage.setItem("veriscan_preferences", JSON.stringify(preferences));
    try { await api.saveProfile(preferences); } catch { /* offline */ }
    await queryClient.invalidateQueries({ queryKey: ["profile"] });
    setSaving(false);
    if (router.canGoBack()) router.back(); else router.replace("/(tabs)/profile");
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + 32 }]}
        showsVerticalScrollIndicator={false}
      >
        <Pressable testID="preferences-back" onPress={() => router.back()} style={styles.backRow}>
          <Ionicons name="close" size={22} color={colors.onSurface} />
          <Text style={styles.backText}>Close</Text>
        </Pressable>
        <Text style={styles.eyebrow}>PERSONAL LENS</Text>
        <Text style={styles.title}>Your clean profile</Text>
        <Text style={styles.body}>
          Update your dietary, health and sensitivity choices anytime. Match scores refresh on your next scan.
        </Text>
        <PreferenceGroup title="Your way of eating" options={DIETARY_OPTIONS} selected={preferences.dietary}
          onToggle={(value) => toggle("dietary", value)} />
        <PreferenceGroup title="Health targets" options={TARGET_OPTIONS} selected={preferences.targets}
          onToggle={(value) => toggle("targets", value)} />
        <PreferenceGroup title="Ingredients to watch" options={SENSITIVITY_OPTIONS} selected={preferences.sensitivities}
          onToggle={(value) => toggle("sensitivities", value)} />
        <Pressable
          testID="preferences-save"
          onPress={save}
          disabled={saving}
          style={[styles.primary, saving && styles.disabled]}
        >
          {saving
            ? <ActivityIndicator color={colors.onBrandPrimary} />
            : <Text style={styles.primaryText}>Save changes</Text>}
        </Pressable>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  content: { paddingHorizontal: 24, paddingTop: 24 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, marginBottom: 6 },
  backText: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1, marginTop: 12 },
  title: { color: colors.onSurface, fontSize: 28, fontWeight: "800", lineHeight: 34, marginTop: 8 },
  body: { color: colors.muted, fontSize: 15, lineHeight: 23, marginTop: 10, marginBottom: 28 },
  primary: { minHeight: 52, borderRadius: 18, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10, paddingHorizontal: 18, marginTop: 12 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 16, fontWeight: "800" },
  disabled: { opacity: 0.6 },
}));

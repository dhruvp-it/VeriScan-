import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { PreferenceGroup } from "@/src/components/preference-group";
import { api } from "@/src/lib/api";
import {
  DIETARY_OPTIONS, SENSITIVITY_OPTIONS, TARGET_OPTIONS,
  emptyPreferences, Preferences,
} from "@/src/lib/preferences";
import { makeStyles, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function Onboarding() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [preferences, setPreferences] = useState<Preferences>(emptyPreferences);
  const [loading, setLoading] = useState(false);

  const toggle = (group: keyof Preferences, value: string) => {
    const current = preferences[group];
    setPreferences({
      ...preferences,
      [group]: current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    });
  };

  const submit = async () => {
    setLoading(true);
    await storage.setItem("veriscan_preferences", JSON.stringify(preferences));
    await storage.setItem("veriscan_onboarded", true);
    try { await api.saveProfile(preferences); } catch { /* guest cached locally */ }
    setLoading(false);
    router.replace("/(tabs)");
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={[styles.content, { paddingBottom: insets.bottom + 32 }]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.brandMark}>
          <Ionicons name="leaf" size={22} color={colors.onBrandPrimary} />
        </View>
        <Text style={styles.eyebrow}>WELCOME TO VERISCAN</Text>
        <Text style={styles.title}>Know what&apos;s in your everyday products.</Text>
        <Text style={styles.body}>
          Build a personal lens for cleaner choices. You can change these preferences anytime.
        </Text>
        <PreferenceGroup title="Your way of eating" options={DIETARY_OPTIONS} selected={preferences.dietary}
          onToggle={(value) => toggle("dietary", value)} />
        <PreferenceGroup title="Health targets" options={TARGET_OPTIONS} selected={preferences.targets}
          onToggle={(value) => toggle("targets", value)} />
        <PreferenceGroup title="Ingredients to watch" options={SENSITIVITY_OPTIONS} selected={preferences.sensitivities}
          onToggle={(value) => toggle("sensitivities", value)} />
        <Pressable
          testID="onboarding-continue"
          accessibilityRole="button"
          onPress={submit}
          disabled={loading}
          style={({ pressed }) => [styles.primary, pressed && styles.pressed, loading && styles.disabled]}
        >
          {loading ? (
            <ActivityIndicator color={colors.onBrandPrimary} />
          ) : (
            <>
              <Text style={styles.primaryText}>Start scanning</Text>
              <Ionicons name="arrow-forward" size={19} color={colors.onBrandPrimary} />
            </>
          )}
        </Pressable>
        <Pressable testID="onboarding-skip" onPress={submit}>
          <Text style={styles.skip}>Skip for now</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  content: { paddingHorizontal: 24, paddingTop: 42 },
  brandMark: { width: 48, height: 48, borderRadius: 16, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", marginBottom: 28 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 30, fontWeight: "800", lineHeight: 36, marginTop: 12 },
  body: { color: colors.muted, fontSize: 15, lineHeight: 23, marginTop: 12, marginBottom: 32 },
  primary: { minHeight: 52, borderRadius: 18, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10, paddingHorizontal: 18, marginTop: 22 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 16, fontWeight: "800" },
  pressed: { opacity: 0.72 },
  disabled: { opacity: 0.6 },
  skip: { color: colors.muted, textAlign: "center", marginTop: 14, paddingVertical: 12, fontWeight: "600" },
}));

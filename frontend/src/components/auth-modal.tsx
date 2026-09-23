import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, Pressable,
  StyleSheet, Text, TextInput, View,
} from "react-native";

import { api, TOKEN_KEY } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

type Props = { visible: boolean; onClose: () => void; onSuccess?: (email: string) => void };

export function AuthModal({ visible, onClose, onSuccess }: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  const router = useRouter();
  const [mode, setMode] = useState<"register" | "login">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  const { data: terms } = useQuery({ queryKey: ["terms-version"], queryFn: () => api.terms(), enabled: visible });
  const { data: privacy } = useQuery({ queryKey: ["privacy-version"], queryFn: () => api.privacy(), enabled: visible });

  if (!visible) return null;

  const submit = async () => {
    if (mode === "register" && !agreed) {
      setError("Please accept the Terms & Privacy Policy to continue.");
      return;
    }
    setBusy(true); setError("");
    try {
      const result = mode === "register"
        ? await api.register(email.trim(), password, terms?.version ?? "1.0.0", privacy?.version ?? "1.0.0")
        : await api.login(email.trim(), password);
      await storage.secureSet(TOKEN_KEY, result.token);
      await queryClient.invalidateQueries();
      onSuccess?.(result.user.email);
      onClose();
      setEmail(""); setPassword(""); setAgreed(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const openLegal = (route: "/legal/terms" | "/legal/privacy") => {
    onClose();
    router.push(route);
  };

  return (
    <View style={styles.backdrop} testID="auth-modal">
      <Pressable style={styles.dismiss} onPress={onClose} testID="auth-dismiss" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={styles.wrap}>
        <View style={styles.card}>
          <View style={styles.headerRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.eyebrow}>{mode === "register" ? "KEEP YOUR HISTORY" : "WELCOME BACK"}</Text>
              <Text style={styles.title}>{mode === "register" ? "Create your account" : "Sign in to VeriScan"}</Text>
            </View>
            <Pressable onPress={onClose} testID="auth-close" style={styles.closeButton}>
              <Ionicons name="close" size={20} color={colors.onSurface} />
            </Pressable>
          </View>
          <Text style={styles.body}>
            {mode === "register"
              ? "We only need your email — no date of birth or personal info."
              : "Continue your ingredient journey."}
          </Text>
          <TextInput
            testID="auth-email" value={email} onChangeText={setEmail}
            autoCapitalize="none" autoCorrect={false} keyboardType="email-address"
            placeholder="Email address" placeholderTextColor={colors.muted} style={styles.input}
          />
          <TextInput
            testID="auth-password" value={password} onChangeText={setPassword}
            secureTextEntry placeholder="Password (6+ characters)"
            placeholderTextColor={colors.muted} style={styles.input}
          />
          {mode === "register" ? (
            <Pressable testID="auth-agree" onPress={() => setAgreed(!agreed)} style={styles.agreeRow}>
              <View style={[styles.checkbox, agreed && styles.checkboxOn]}>
                {agreed ? <Ionicons name="checkmark" size={16} color={colors.onBrandPrimary} /> : null}
              </View>
              <Text style={styles.agreeText}>
                I agree to the{" "}
                <Text style={styles.link} onPress={() => openLegal("/legal/terms")}>Terms</Text>
                {" "}and{" "}
                <Text style={styles.link} onPress={() => openLegal("/legal/privacy")}>Privacy Policy</Text>.
              </Text>
            </Pressable>
          ) : (
            <Pressable
              testID="auth-forgot"
              onPress={() => { onClose(); router.push("/forgot-password"); }}
              style={styles.forgotButton}
            >
              <Text style={styles.link}>Forgot password?</Text>
            </Pressable>
          )}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable
            testID="auth-submit"
            onPress={submit}
            disabled={busy || !email || password.length < 6 || (mode === "register" && !agreed)}
            style={[
              styles.primaryButton,
              (busy || !email || password.length < 6 || (mode === "register" && !agreed)) && styles.primaryDisabled,
            ]}
          >
            {busy
              ? <ActivityIndicator color={colors.onBrandPrimary} />
              : <Text style={styles.primaryText}>{mode === "register" ? "Create account" : "Sign in"}</Text>}
          </Pressable>
          <Pressable onPress={() => setMode(mode === "register" ? "login" : "register")} testID="auth-mode-toggle">
            <Text style={styles.link}>
              {mode === "register" ? "Already have an account? Sign in" : "Need an account? Create one"}
            </Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(17,19,17,0.36)", justifyContent: "flex-end", zIndex: 40 },
  dismiss: { flex: 1 },
  wrap: { width: "100%" },
  card: { backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 22, paddingBottom: 32 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 22, fontWeight: "800", marginTop: 4 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21, marginTop: 10, marginBottom: 6 },
  closeButton: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  input: { height: 50, borderRadius: 14, backgroundColor: colors.surfaceTertiary, paddingHorizontal: 14, color: colors.onSurface, marginTop: 12, fontSize: 15 },
  error: { color: colors.error, fontSize: 13, lineHeight: 19, marginTop: 10 },
  primaryButton: { minHeight: 52, borderRadius: 18, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10, paddingHorizontal: 18, marginTop: 20 },
  primaryDisabled: { opacity: 0.5 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 16, fontWeight: "800" },
  link: { color: colors.brandPrimary, fontWeight: "700", fontSize: 14, textAlign: "center", paddingVertical: 8 },
  forgotButton: { marginTop: 8, alignItems: "flex-end" },
  agreeRow: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 14 },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center" },
  checkboxOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  agreeText: { flex: 1, color: colors.onSurfaceSecondary, fontSize: 13, lineHeight: 19 },
}));

import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
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
  const [mode, setMode] = useState<"register" | "login">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const queryClient = useQueryClient();

  if (!visible) return null;

  const submit = async () => {
    setBusy(true); setError("");
    try {
      const result = mode === "register"
        ? await api.register(email.trim(), password)
        : await api.login(email.trim(), password);
      await storage.secureSet(TOKEN_KEY, result.token);
      await queryClient.invalidateQueries();
      onSuccess?.(result.user.email);
      onClose();
      setEmail(""); setPassword("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.backdrop} testID="auth-modal">
      <Pressable style={styles.dismiss} onPress={onClose} testID="auth-dismiss" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={styles.wrap}>
        <View style={styles.card}>
          <View style={styles.headerRow}>
            <View>
              <Text style={styles.eyebrow}>{mode === "register" ? "KEEP YOUR HISTORY" : "WELCOME BACK"}</Text>
              <Text style={styles.title}>{mode === "register" ? "Create your account" : "Sign in to VeriScan"}</Text>
            </View>
            <Pressable onPress={onClose} testID="auth-close" style={styles.closeButton}>
              <Ionicons name="close" size={20} color={colors.onSurface} />
            </Pressable>
          </View>
          <Text style={styles.body}>
            {mode === "register"
              ? "Your first three scans are free. Sign up to keep going and sync your clean profile."
              : "Continue your ingredient journey."}
          </Text>
          <TextInput
            testID="auth-email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            placeholder="Email address"
            placeholderTextColor={colors.muted}
            style={styles.input}
          />
          <TextInput
            testID="auth-password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="Password (6+ characters)"
            placeholderTextColor={colors.muted}
            style={styles.input}
          />
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <Pressable
            testID="auth-submit"
            onPress={submit}
            disabled={busy || !email || password.length < 6}
            style={[styles.primaryButton, (busy || !email || password.length < 6) && styles.primaryDisabled]}
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
  link: { color: colors.brandPrimary, fontWeight: "700", fontSize: 14, textAlign: "center", marginTop: 16, paddingVertical: 8 },
}));

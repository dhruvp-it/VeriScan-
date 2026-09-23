import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView,
  StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function ForgotPassword() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [step, setStep] = useState<"request" | "reset">("request");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const sendOtp = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      await api.forgotPassword(email.trim());
      setMessage("If that email is in our system, we've sent a 6-digit code. It expires in 10 minutes.");
      setStep("reset");
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(false); }
  };

  const resetPassword = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      await api.resetPassword(email.trim(), otp.trim(), password);
      setMessage("Password updated. You can now sign in with the new password.");
      setTimeout(() => router.back(), 1200);
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + 32 }]}>
          <Pressable testID="forgot-back" onPress={() => router.back()} style={styles.backRow}>
            <Ionicons name="arrow-back" size={21} color={colors.onSurface} />
            <Text style={styles.backText}>Back</Text>
          </Pressable>
          <Text style={styles.eyebrow}>ACCOUNT RECOVERY</Text>
          <Text style={styles.title}>{step === "request" ? "Reset your password" : "Enter the code we sent you"}</Text>
          <Text style={styles.body}>
            {step === "request"
              ? "Enter your account email. We'll send a 6-digit code to that address."
              : "The code expires in 10 minutes. If it doesn't arrive, request a new one."}
          </Text>

          <TextInput
            testID="forgot-email" value={email} onChangeText={setEmail}
            autoCapitalize="none" autoCorrect={false} keyboardType="email-address"
            placeholder="Email address" placeholderTextColor={colors.muted} style={styles.input}
            editable={step === "request"}
          />
          {step === "reset" ? (
            <>
              <TextInput
                testID="forgot-otp" value={otp} onChangeText={setOtp} keyboardType="number-pad"
                placeholder="6-digit code" placeholderTextColor={colors.muted} style={styles.input} maxLength={6}
              />
              <TextInput
                testID="forgot-password" value={password} onChangeText={setPassword}
                secureTextEntry placeholder="New password (6+ characters)"
                placeholderTextColor={colors.muted} style={styles.input}
              />
            </>
          ) : null}

          {message ? <Text style={styles.message}>{message}</Text> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable
            testID="forgot-submit"
            onPress={step === "request" ? sendOtp : resetPassword}
            disabled={busy || !email || (step === "reset" && (otp.length !== 6 || password.length < 6))}
            style={[styles.primary,
              (busy || !email || (step === "reset" && (otp.length !== 6 || password.length < 6))) && styles.disabled]}
          >
            {busy
              ? <ActivityIndicator color={colors.onBrandPrimary} />
              : <Text style={styles.primaryText}>{step === "request" ? "Send code" : "Reset password"}</Text>}
          </Pressable>

          {step === "reset" ? (
            <Pressable testID="forgot-resend" onPress={() => setStep("request")}>
              <Text style={styles.link}>Use a different email</Text>
            </Pressable>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 24, paddingTop: 24 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44 },
  backText: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1, marginTop: 8 },
  title: { color: colors.onSurface, fontSize: 26, fontWeight: "800", marginTop: 8, marginBottom: 10 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 22, marginBottom: 18 },
  input: { height: 50, borderRadius: 14, backgroundColor: colors.surfaceTertiary, paddingHorizontal: 14, color: colors.onSurface, marginTop: 12, fontSize: 15 },
  message: { color: colors.brandPrimary, fontSize: 13, marginTop: 14 },
  error: { color: colors.error, fontSize: 13, marginTop: 14 },
  primary: { minHeight: 52, borderRadius: 18, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10, paddingHorizontal: 18, marginTop: 20 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 16, fontWeight: "800" },
  disabled: { opacity: 0.55 },
  link: { color: colors.brandPrimary, textAlign: "center", marginTop: 14, paddingVertical: 8, fontWeight: "700" },
}));

import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useEntitlement } from "@/src/hooks/use-entitlement";
import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

type Step = "idle" | "email_otp" | "phone_otp";

export default function AdminProfileRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: entitlement } = useEntitlement();
  const isAdmin = entitlement?.role === "admin";

  const { data: profile, isLoading } = useQuery({
    queryKey: ["admin-profile"],
    queryFn: () => api.adminProfile(),
    enabled: isAdmin,
  });

  const [step, setStep] = useState<Step>("idle");
  const [sessionId, setSessionId] = useState("");
  const [password, setPassword] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [currentOtp, setCurrentOtp] = useState("");
  const [newOtp, setNewOtp] = useState("");
  const [phoneOtp, setPhoneOtp] = useState("");
  const [statusMsg, setStatusMsg] = useState("");

  const startEmailChange = useMutation({
    mutationFn: () => api.adminChangeEmailStart(newEmail.trim().toLowerCase(), password),
    onSuccess: (r) => { setSessionId(r.session_id); setStep("email_otp"); setStatusMsg("Codes sent to your current and new email addresses."); },
    onError: (e) => setStatusMsg((e as Error).message),
  });
  const confirmEmailChange = useMutation({
    mutationFn: () => api.adminChangeEmailConfirm(sessionId, currentOtp, newOtp),
    onSuccess: (r) => {
      setStep("idle"); setSessionId(""); setPassword(""); setNewEmail(""); setCurrentOtp(""); setNewOtp("");
      setStatusMsg(`✅ Admin email updated to ${r.new_email}. Please sign in again.`);
      queryClient.invalidateQueries({ queryKey: ["admin-profile"] });
    },
    onError: (e) => setStatusMsg((e as Error).message),
  });
  const startPhoneChange = useMutation({
    mutationFn: () => api.adminChangePhoneStart(newPhone.trim(), password),
    onSuccess: (r) => { setSessionId(r.session_id); setStep("phone_otp"); setStatusMsg(r.delivery_notice); },
    onError: (e) => setStatusMsg((e as Error).message),
  });
  const confirmPhoneChange = useMutation({
    mutationFn: () => api.adminChangePhoneConfirm(sessionId, phoneOtp),
    onSuccess: (r) => {
      setStep("idle"); setSessionId(""); setPassword(""); setNewPhone(""); setPhoneOtp("");
      setStatusMsg(`✅ Admin phone updated to ${r.new_phone}.`);
      queryClient.invalidateQueries({ queryKey: ["admin-profile"] });
    },
    onError: (e) => setStatusMsg((e as Error).message),
  });
  const sendReport = useMutation({
    mutationFn: () => api.sendMonthlyReportNow(),
    onSuccess: (r) => Alert.alert("Report sent", `Monthly analytics report sent to ${r.sent} admin${r.sent === 1 ? "" : "s"}.`),
    onError: (e) => Alert.alert("Send failed", (e as Error).message),
  });

  if (!isAdmin) {
    return (
      <View style={[styles.root, { paddingTop: insets.top, justifyContent: "center", alignItems: "center", padding: 24 }]}>
        <Ionicons name="shield-outline" size={40} color={colors.brandPrimary} />
        <Text style={styles.title}>Admin only</Text>
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="admin-profile-back" onPress={() => router.back()} style={styles.roundButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Admin profile</Text>
        <View style={{ width: 44 }} />
      </View>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {isLoading || !profile ? (
          <ActivityIndicator color={colors.brandPrimary} style={{ marginTop: 40 }} />
        ) : (
          <>
            <View style={styles.card}>
              <Text style={styles.label}>Current email</Text>
              <Text style={styles.value}>{profile.email}</Text>
              <Text style={styles.label}>Phone number</Text>
              <Text style={styles.value}>{profile.phone_number ?? "Not set"}</Text>
              {profile.phone_verified_at ? (
                <Text style={styles.verified}>Verified {new Date(profile.phone_verified_at).toLocaleDateString()}</Text>
              ) : null}
            </View>

            {step === "idle" ? (
              <>
                <Text style={styles.sectionTitle}>Change email</Text>
                <TextInput
                  testID="admin-new-email"
                  value={newEmail}
                  onChangeText={setNewEmail}
                  placeholder="new@example.com"
                  placeholderTextColor={colors.muted}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  style={styles.input}
                />
                <TextInput
                  testID="admin-password-email"
                  value={password}
                  onChangeText={setPassword}
                  placeholder="Confirm your password"
                  placeholderTextColor={colors.muted}
                  secureTextEntry
                  style={styles.input}
                />
                <Pressable
                  testID="admin-change-email-start"
                  onPress={() => { setStatusMsg(""); startEmailChange.mutate(); }}
                  disabled={startEmailChange.isPending || !newEmail.trim() || !password}
                  style={[styles.primary, (!newEmail.trim() || !password) && styles.disabled]}
                >
                  {startEmailChange.isPending ? <ActivityIndicator color={colors.onBrandPrimary} /> : (
                    <>
                      <Ionicons name="mail-outline" size={18} color={colors.onBrandPrimary} />
                      <Text style={styles.primaryText}>Send verification codes</Text>
                    </>
                  )}
                </Pressable>

                <Text style={styles.sectionTitle}>Change phone number</Text>
                <TextInput
                  testID="admin-new-phone"
                  value={newPhone}
                  onChangeText={setNewPhone}
                  placeholder="+91 9876543210"
                  placeholderTextColor={colors.muted}
                  keyboardType="phone-pad"
                  style={styles.input}
                />
                <TextInput
                  testID="admin-password-phone"
                  value={password}
                  onChangeText={setPassword}
                  placeholder="Confirm your password"
                  placeholderTextColor={colors.muted}
                  secureTextEntry
                  style={styles.input}
                />
                <Pressable
                  testID="admin-change-phone-start"
                  onPress={() => { setStatusMsg(""); startPhoneChange.mutate(); }}
                  disabled={startPhoneChange.isPending || !newPhone.trim() || !password}
                  style={[styles.primary, (!newPhone.trim() || !password) && styles.disabled]}
                >
                  {startPhoneChange.isPending ? <ActivityIndicator color={colors.onBrandPrimary} /> : (
                    <>
                      <Ionicons name="call-outline" size={18} color={colors.onBrandPrimary} />
                      <Text style={styles.primaryText}>Send verification code</Text>
                    </>
                  )}
                </Pressable>

                <Text style={styles.sectionTitle}>Monthly analytics email</Text>
                <Text style={styles.body}>Automatically sent to every admin on the 1st of each month. You can trigger a manual send now.</Text>
                <Pressable
                  testID="admin-send-report"
                  onPress={() => sendReport.mutate()}
                  disabled={sendReport.isPending}
                  style={[styles.outline, sendReport.isPending && styles.disabled]}
                >
                  <Ionicons name="paper-plane-outline" size={17} color={colors.brandPrimary} />
                  <Text style={styles.outlineText}>Send last month's report now</Text>
                </Pressable>
              </>
            ) : step === "email_otp" ? (
              <>
                <Text style={styles.sectionTitle}>Enter both codes</Text>
                <Text style={styles.body}>Codes sent to your current admin email and to {newEmail}. Both must match.</Text>
                <TextInput
                  testID="admin-email-otp-current"
                  value={currentOtp}
                  onChangeText={setCurrentOtp}
                  placeholder="Code from current email"
                  placeholderTextColor={colors.muted}
                  keyboardType="number-pad"
                  maxLength={6}
                  style={styles.input}
                />
                <TextInput
                  testID="admin-email-otp-new"
                  value={newOtp}
                  onChangeText={setNewOtp}
                  placeholder="Code from new email"
                  placeholderTextColor={colors.muted}
                  keyboardType="number-pad"
                  maxLength={6}
                  style={styles.input}
                />
                <Pressable
                  testID="admin-email-otp-confirm"
                  onPress={() => { setStatusMsg(""); confirmEmailChange.mutate(); }}
                  disabled={confirmEmailChange.isPending || currentOtp.length !== 6 || newOtp.length !== 6}
                  style={[styles.primary, (currentOtp.length !== 6 || newOtp.length !== 6) && styles.disabled]}
                >
                  {confirmEmailChange.isPending ? <ActivityIndicator color={colors.onBrandPrimary} /> : (
                    <Text style={styles.primaryText}>Confirm email change</Text>
                  )}
                </Pressable>
                <Pressable onPress={() => { setStep("idle"); setStatusMsg(""); }} style={styles.outline}>
                  <Text style={styles.outlineText}>Cancel</Text>
                </Pressable>
              </>
            ) : (
              <>
                <Text style={styles.sectionTitle}>Enter verification code</Text>
                <Text style={styles.body}>Code delivered to {profile.email}. Enter it below to confirm your new phone number.</Text>
                <TextInput
                  testID="admin-phone-otp"
                  value={phoneOtp}
                  onChangeText={setPhoneOtp}
                  placeholder="6-digit code"
                  placeholderTextColor={colors.muted}
                  keyboardType="number-pad"
                  maxLength={6}
                  style={styles.input}
                />
                <Pressable
                  testID="admin-phone-otp-confirm"
                  onPress={() => { setStatusMsg(""); confirmPhoneChange.mutate(); }}
                  disabled={confirmPhoneChange.isPending || phoneOtp.length !== 6}
                  style={[styles.primary, phoneOtp.length !== 6 && styles.disabled]}
                >
                  {confirmPhoneChange.isPending ? <ActivityIndicator color={colors.onBrandPrimary} /> : (
                    <Text style={styles.primaryText}>Confirm phone change</Text>
                  )}
                </Pressable>
                <Pressable onPress={() => { setStep("idle"); setStatusMsg(""); }} style={styles.outline}>
                  <Text style={styles.outlineText}>Cancel</Text>
                </Pressable>
              </>
            )}
            {statusMsg ? <Text style={styles.status}>{statusMsg}</Text> : null}
          </>
        )}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingVertical: 10 },
  roundButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: "800" },
  scroll: { paddingHorizontal: 20, paddingBottom: 40 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 18, padding: 16, marginTop: 6, marginBottom: 20, gap: 4 },
  label: { color: colors.muted, fontSize: 11, fontWeight: "800", letterSpacing: 0.6, marginTop: 8 },
  value: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  verified: { color: colors.success ?? colors.brandPrimary, fontSize: 12, fontWeight: "700", marginTop: 4 },
  sectionTitle: { color: colors.onSurface, fontSize: 15, fontWeight: "800", marginTop: 18, marginBottom: 8 },
  body: { color: colors.muted, fontSize: 13, lineHeight: 19, marginBottom: 10 },
  input: { minHeight: 48, borderRadius: 14, backgroundColor: colors.surfaceSecondary, paddingHorizontal: 14, color: colors.onSurface, fontSize: 15, marginTop: 6 },
  primary: { minHeight: 48, borderRadius: 14, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8, marginTop: 10 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 14, fontWeight: "800" },
  outline: { minHeight: 44, borderRadius: 14, borderWidth: 1, borderColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8, marginTop: 10 },
  outlineText: { color: colors.brandPrimary, fontSize: 13, fontWeight: "800" },
  disabled: { opacity: 0.55 },
  status: { color: colors.brandPrimary, fontSize: 13, marginTop: 16, textAlign: "center", lineHeight: 19 },
}));

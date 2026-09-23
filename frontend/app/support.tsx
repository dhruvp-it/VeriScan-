import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView,
  StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useEntitlement } from "@/src/hooks/use-entitlement";
import { api, SupportTicket } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const CATEGORIES = ["general", "billing", "account", "product data", "report abuse"] as const;

export default function SupportRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: entitlement } = useEntitlement();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState<string>("general");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");

  const { data: myTickets } = useQuery<SupportTicket[]>({
    queryKey: ["my-support"],
    queryFn: () => api.mySupport(),
    enabled: entitlement?.registered ?? false,
    initialData: [],
  });

  const submit = async () => {
    setBusy(true); setFeedback("");
    try {
      await api.submitSupport(subject.trim(), message.trim(), category);
      setSubject(""); setMessage("");
      setFeedback("Thanks — we've logged your ticket. Our team will review it soon.");
      queryClient.invalidateQueries({ queryKey: ["my-support"] });
    } catch (e) {
      setFeedback((e as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.header}>
        <Pressable testID="support-back" onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Support</Text>
      </View>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={[styles.scroll, { paddingBottom: insets.bottom + 32 }]}>
          <Text style={styles.eyebrow}>NEW TICKET</Text>
          <Text style={styles.subtitle}>How can we help?</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
            {CATEGORIES.map((cat) => (
              <Pressable
                key={cat}
                onPress={() => setCategory(cat)}
                testID={`support-cat-${cat.replace(/\s+/g, "-")}`}
                style={[styles.chip, category === cat && styles.chipOn]}
              >
                <Text style={[styles.chipText, category === cat && styles.chipTextOn]}>{cat}</Text>
              </Pressable>
            ))}
          </ScrollView>
          <TextInput
            testID="support-subject" value={subject} onChangeText={setSubject}
            placeholder="Subject" placeholderTextColor={colors.muted} style={styles.input}
          />
          <TextInput
            testID="support-message" value={message} onChangeText={setMessage}
            placeholder="Describe the issue" placeholderTextColor={colors.muted}
            multiline style={[styles.input, styles.messageInput]}
          />
          {feedback ? <Text style={styles.feedback}>{feedback}</Text> : null}
          <Pressable
            testID="support-submit"
            onPress={submit}
            disabled={busy || subject.trim().length < 3 || message.trim().length < 5}
            style={[styles.primary,
              (busy || subject.trim().length < 3 || message.trim().length < 5) && styles.disabled]}
          >
            {busy ? <ActivityIndicator color={colors.onBrandPrimary} /> : <Text style={styles.primaryText}>Send</Text>}
          </Pressable>

          {(myTickets?.length ?? 0) > 0 ? (
            <>
              <Text style={[styles.eyebrow, { marginTop: 28 }]}>YOUR TICKETS</Text>
              {myTickets!.map((ticket) => (
                <View key={ticket.id} style={styles.ticket} testID={`ticket-${ticket.id}`}>
                  <View style={styles.ticketHeaderRow}>
                    <Text style={styles.ticketSubject}>{ticket.subject}</Text>
                    <View style={[styles.statusPill, ticket.status === "resolved" && styles.statusPillResolved]}>
                      <Text style={[styles.statusText, ticket.status === "resolved" && styles.statusTextResolved]}>
                        {ticket.status}
                      </Text>
                    </View>
                  </View>
                  <Text style={styles.ticketBody}>{ticket.message}</Text>
                  {ticket.admin_note ? <Text style={styles.ticketNote}>Response: {ticket.admin_note}</Text> : null}
                </View>
              ))}
            </>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  backButton: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: "800" },
  scroll: { paddingHorizontal: 20, paddingTop: 20 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  subtitle: { color: colors.onSurface, fontSize: 22, fontWeight: "800", marginTop: 8, marginBottom: 12 },
  chipRow: { gap: 8, paddingRight: 4, minHeight: 44, paddingVertical: 4 },
  chip: { minHeight: 36, paddingHorizontal: 12, borderRadius: 18, borderWidth: 1, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center", flexShrink: 0 },
  chipOn: { backgroundColor: colors.brandTertiary, borderColor: colors.brandSecondary },
  chipText: { color: colors.onSurfaceSecondary, fontSize: 13, fontWeight: "700" },
  chipTextOn: { color: colors.onBrandTertiary },
  input: { minHeight: 50, borderRadius: 14, backgroundColor: colors.surfaceTertiary, paddingHorizontal: 14, color: colors.onSurface, marginTop: 12, fontSize: 15 },
  messageInput: { minHeight: 120, paddingTop: 14, textAlignVertical: "top" },
  feedback: { color: colors.onSurfaceSecondary, fontSize: 13, marginTop: 12 },
  primary: { minHeight: 50, borderRadius: 16, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", marginTop: 16 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 15, fontWeight: "800" },
  disabled: { opacity: 0.55 },
  ticket: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, padding: 14, marginTop: 10 },
  ticketHeaderRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  ticketSubject: { color: colors.onSurface, fontSize: 14, fontWeight: "700", flex: 1, paddingRight: 8 },
  statusPill: { backgroundColor: colors.warning, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  statusPillResolved: { backgroundColor: colors.success },
  statusText: { color: colors.onWarning, fontSize: 10, fontWeight: "900", textTransform: "uppercase", letterSpacing: 0.6 },
  statusTextResolved: { color: colors.onSuccess },
  ticketBody: { color: colors.onSurfaceSecondary, fontSize: 13, lineHeight: 20 },
  ticketNote: { color: colors.brandPrimary, fontSize: 13, marginTop: 8, fontStyle: "italic" },
}));

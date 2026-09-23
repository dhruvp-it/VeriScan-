import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import { CameraView, useCameraPermissions } from "expo-camera";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useRef, useState } from "react";
import {
  ActivityIndicator, Linking, Platform, Pressable, ScrollView,
  StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

const STEPS = [
  "Confirm barcode",
  "Product front",
  "Nutrition table",
  "Ingredients list",
  "Certification badges",
];

export default function ContributeRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { barcode } = useLocalSearchParams<{ barcode: string }>();
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  const next = async () => {
    if (step === 0) { setStep(1); return; }
    setBusy(true);
    try {
      if (Platform.OS !== "web" && permission?.granted && cameraRef.current) {
        const photo = await cameraRef.current.takePictureAsync({ base64: true, quality: 0.45 });
        if (photo?.base64) setImages((prev) => [...prev, photo.base64!]);
      }
      if (step === STEPS.length - 1) {
        const result = await api.contribute({ barcode: barcode as string, product_name: name, notes, images });
        if (result.product) {
          setMessage("Analysis ready. Opening report…");
          queryClient.setQueryData(["product", barcode], result.product);
          queryClient.invalidateQueries({ queryKey: ["history"] });
          setTimeout(() => router.replace({ pathname: "/product/[barcode]", params: { barcode: barcode as string } }), 700);
        } else {
          setMessage(result.ocr_error
            ? `Couldn't read the label clearly: ${result.ocr_error}. We've queued it for manual review.`
            : "Thanks for contributing. We'll verify and add this product soon.");
          setTimeout(() => router.back(), 1500);
        }
      } else {
        setStep(step + 1);
      }
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Pressable testID="contribute-back" onPress={() => router.back()} style={styles.backRow}>
          <Ionicons name="arrow-back" size={21} color={colors.onSurface} />
          <Text style={styles.backText}>Back</Text>
        </Pressable>
        <Text style={styles.eyebrow}>COMMUNITY CONTRIBUTION</Text>
        <Text style={styles.title}>Help complete this product.</Text>
        <Text style={styles.body}>
          Barcode {barcode} is not in our registry yet. Add clear label photos and our team can verify it.
        </Text>

        <View style={styles.stepper}>
          {STEPS.map((label, index) => (
            <View key={label} style={styles.stepItem}>
              <View style={[styles.stepDot, index <= step && styles.stepDotActive]}>
                <Text style={[styles.stepNumber, index <= step && styles.stepNumberActive]}>{index + 1}</Text>
              </View>
              <Text style={[styles.stepLabel, index === step && styles.stepLabelActive]}>{label}</Text>
            </View>
          ))}
        </View>

        {step === 0 ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Ready to contribute?</Text>
            <Text style={styles.body}>
              We&apos;ll guide you through five short captures: the front of pack, nutrition label, ingredients list and any certification badges.
            </Text>
            <TextInput
              testID="contribute-product-name"
              value={name}
              onChangeText={setName}
              placeholder="Product name (optional)"
              placeholderTextColor={colors.muted}
              style={styles.input}
            />
            <TextInput
              testID="contribute-notes"
              value={notes}
              onChangeText={setNotes}
              placeholder="Any notes for the verifier"
              placeholderTextColor={colors.muted}
              style={[styles.input, styles.notesInput]}
              multiline
            />
          </View>
        ) : (
          <View style={styles.card}>
            {permission?.granted && Platform.OS !== "web" ? (
              <CameraView ref={cameraRef} style={styles.camera} facing="back" />
            ) : (
              <View style={styles.cameraFallback}>
                <Ionicons name="camera-outline" size={42} color={colors.brandPrimary} />
                <Text style={styles.cardTitle}>
                  {Platform.OS === "web" ? "Use your phone for image capture" : "Camera permission needed"}
                </Text>
                {Platform.OS !== "web" && permission?.canAskAgain !== false && (
                  <Pressable onPress={requestPermission} style={styles.smallButton}>
                    <Text style={styles.smallButtonText}>Enable camera</Text>
                  </Pressable>
                )}
                {permission?.canAskAgain === false && (
                  <Pressable onPress={() => Linking.openSettings()} style={styles.smallButton}>
                    <Text style={styles.smallButtonText}>Open settings</Text>
                  </Pressable>
                )}
              </View>
            )}
            <Text style={styles.captureTitle}>{STEPS[step]}</Text>
            <Text style={styles.muted}>Keep the label flat, bright, and fully inside the frame.</Text>
          </View>
        )}

        {message ? <Text style={styles.message} testID="contribute-message">{message}</Text> : null}

        <Pressable
          testID="contribute-next"
          onPress={next}
          disabled={busy}
          style={[styles.primary, busy && styles.disabled]}
        >
          {busy ? (
            <ActivityIndicator color={colors.onBrandPrimary} />
          ) : (
            <>
              <Text style={styles.primaryText}>
                {step === STEPS.length - 1 ? "Submit for verification" : step === 0 ? "Begin guided capture" : "Capture & continue"}
              </Text>
              <Ionicons name="arrow-forward" size={19} color={colors.onBrandPrimary} />
            </>
          )}
        </Pressable>
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 40 },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44, marginBottom: 12 },
  backText: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 26, fontWeight: "800", marginTop: 8 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21, marginTop: 10 },
  stepper: { gap: 12, marginTop: 22, marginBottom: 18 },
  stepItem: { flexDirection: "row", alignItems: "center", gap: 11 },
  stepDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  stepDotActive: { backgroundColor: colors.brandPrimary },
  stepNumber: { color: colors.muted, fontWeight: "800", fontSize: 12 },
  stepNumberActive: { color: colors.onBrandPrimary },
  stepLabel: { color: colors.muted, fontSize: 13 },
  stepLabelActive: { color: colors.onSurface, fontWeight: "800" },
  card: { borderRadius: 22, backgroundColor: colors.surfaceSecondary, padding: 16, marginBottom: 12 },
  cardTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  input: { height: 50, borderRadius: 14, backgroundColor: colors.surface, paddingHorizontal: 14, color: colors.onSurface, marginTop: 12, fontSize: 15 },
  notesInput: { height: 90, paddingTop: 14, textAlignVertical: "top" },
  camera: { height: 250, borderRadius: 17, overflow: "hidden" },
  cameraFallback: { height: 250, alignItems: "center", justifyContent: "center", gap: 10 },
  captureTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800", marginTop: 15, marginBottom: 4 },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  message: { color: colors.brandPrimary, fontSize: 14, fontWeight: "700", marginTop: 12, marginBottom: 6 },
  smallButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 16 },
  smallButtonText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
  primary: { minHeight: 52, borderRadius: 18, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10, paddingHorizontal: 18, marginTop: 12 },
  primaryText: { color: colors.onBrandPrimary, fontSize: 16, fontWeight: "800" },
  disabled: { opacity: 0.6 },
}));

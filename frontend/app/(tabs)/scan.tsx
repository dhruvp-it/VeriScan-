import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import { useRouter } from "expo-router";
import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator, Linking, Platform, Pressable, ScrollView, StyleSheet,
  Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AuthModal } from "@/src/components/auth-modal";
import { api } from "@/src/lib/api";
import { makeStyles, useTheme } from "@/src/theme";

export default function ScanTab() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [manualBarcode, setManualBarcode] = useState("");
  const [torch, setTorch] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();
  const inflight = useRef(false);

  const lookup = useCallback(async (raw: string) => {
    const barcode = raw.trim();
    if (!barcode) { setMessage("Enter a barcode to continue."); return; }
    if (inflight.current) return;
    inflight.current = true;
    setLoading(true); setMessage("");
    try {
      const product = await api.lookup(barcode);
      queryClient.setQueryData(["product", barcode], product);
      await queryClient.invalidateQueries({ queryKey: ["entitlement"] });
      await queryClient.invalidateQueries({ queryKey: ["history"] });
      router.push({ pathname: "/product/[barcode]", params: { barcode } });
    } catch (error) {
      const typed = error as Error & { status?: number };
      if (typed.status === 404) {
        router.push({ pathname: "/contribute/[barcode]", params: { barcode } });
      } else if (typed.status === 401) {
        setAuthOpen(true);
      } else if (typed.status === 402) {
        router.push("/plans");
        setMessage(typed.message);
      } else {
        setMessage(typed.message);
      }
    } finally {
      setLoading(false);
      setTimeout(() => { inflight.current = false; }, 1200);
    }
  }, [queryClient, router]);

  const onBarcodeScanned = ({ data }: { data: string }) => {
    if (inflight.current) return;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    lookup(data);
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.eyebrow}>SCAN & ANALYZE</Text>
            <Text style={styles.title}>Find your next better choice.</Text>
          </View>
          <Pressable
            testID="scan-torch"
            onPress={() => setTorch((v) => !v)}
            style={styles.roundButton}
            accessibilityRole="button"
            accessibilityLabel="Toggle flashlight"
          >
            <Ionicons name={torch ? "flash" : "flash-outline"} size={21} color={colors.onSurface} />
          </Pressable>
        </View>

        <View style={styles.cameraCard}>
          {permission?.granted && Platform.OS !== "web" ? (
            <CameraView
              style={styles.camera}
              facing="back"
              enableTorch={torch}
              onBarcodeScanned={inflight.current ? undefined : onBarcodeScanned}
              barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e"] }}
            />
          ) : (
            <View style={styles.cameraFallback}>
              <Ionicons name="camera-outline" size={42} color={colors.brandPrimary} />
              <Text style={styles.cameraFallbackTitle}>
                {permission?.canAskAgain === false ? "Camera access is off" : "Ready when you are"}
              </Text>
              <Text style={styles.muted}>
                {Platform.OS === "web"
                  ? "Use manual entry in the preview, then scan from your phone."
                  : "Allow camera access to scan a barcode instantly."}
              </Text>
              {Platform.OS !== "web" && permission?.canAskAgain !== false && (
                <Pressable testID="enable-camera" onPress={requestPermission} style={styles.smallButton}>
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
          <View style={styles.scanFrame} />
        </View>

        <Text style={styles.helper}>Align an EAN or UPC barcode inside the frame.</Text>
        <View style={styles.manualRow}>
          <TextInput
            testID="manual-barcode-input"
            value={manualBarcode}
            onChangeText={setManualBarcode}
            keyboardType="number-pad"
            placeholder="Or enter barcode manually"
            placeholderTextColor={colors.muted}
            style={styles.manualInput}
          />
          <Pressable
            testID="manual-lookup"
            accessibilityLabel="Look up barcode"
            onPress={() => lookup(manualBarcode)}
            style={styles.manualButton}
          >
            {loading ? <ActivityIndicator color={colors.onBrandPrimary} /> : <Ionicons name="arrow-forward" size={21} color={colors.onBrandPrimary} />}
          </Pressable>
        </View>
        {message ? <Text style={styles.error} testID="scan-error">{message}</Text> : null}
      </ScrollView>
      <AuthModal visible={authOpen} onClose={() => setAuthOpen(false)} />
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 32 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 22 },
  eyebrow: { color: colors.brandPrimary, fontSize: 11, fontWeight: "800", letterSpacing: 1.1 },
  title: { color: colors.onSurface, fontSize: 27, fontWeight: "800", marginTop: 8, maxWidth: 300 },
  roundButton: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  cameraCard: { height: 330, overflow: "hidden", borderRadius: 24, backgroundColor: colors.surfaceSecondary, position: "relative" },
  camera: { flex: 1 },
  cameraFallback: { flex: 1, alignItems: "center", justifyContent: "center", padding: 26, gap: 9 },
  cameraFallbackTitle: { color: colors.onSurface, fontSize: 18, fontWeight: "700" },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19, textAlign: "center" },
  scanFrame: { position: "absolute", alignSelf: "center", top: 79, width: 210, height: 160, borderWidth: 2, borderColor: colors.onBrandPrimary, borderRadius: 20 },
  helper: { textAlign: "center", color: colors.muted, fontSize: 13, marginVertical: 14 },
  manualRow: { flexDirection: "row", gap: 10 },
  manualInput: { flex: 1, height: 52, borderRadius: 16, paddingHorizontal: 15, backgroundColor: colors.surfaceTertiary, color: colors.onSurface, fontSize: 15 },
  manualButton: { width: 52, height: 52, borderRadius: 16, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  error: { color: colors.error, fontSize: 13, lineHeight: 19, marginTop: 10 },
  smallButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 16 },
  smallButtonText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
}));

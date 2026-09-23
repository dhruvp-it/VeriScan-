import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { BetterForYou } from "@/src/components/better-for-you";
import { IngredientSheet } from "@/src/components/ingredient-sheet";
import { NutritionCard } from "@/src/components/nutrition-card";
import { PriceBenchmark } from "@/src/components/price-benchmark";
import { PriceComparison } from "@/src/components/price-comparison";
import { RegulatoryBadges } from "@/src/components/regulatory-badges";
import { useEntitlement } from "@/src/hooks/use-entitlement";
import { api, Ingredient, Product, WatchlistItem } from "@/src/lib/api";
import { scoreColor, scoreLabel } from "@/src/lib/scoring";
import { makeStyles, useTheme } from "@/src/theme";

export default function ProductRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { barcode } = useLocalSearchParams<{ barcode: string }>();
  const [selected, setSelected] = useState<Ingredient | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState("");
  const [reportMessage, setReportMessage] = useState("");
  const { data: entitlement } = useEntitlement();
  const { data: product, isLoading, error } = useQuery<Product>({
    queryKey: ["product", barcode],
    queryFn: () => api.lookup(barcode as string),
    enabled: !!barcode,
    staleTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
  });

  const { data: watchlist } = useQuery<WatchlistItem[]>({
    queryKey: ["watchlist"],
    queryFn: () => api.watchlist(),
    enabled: entitlement?.registered ?? false,
    initialData: [],
  });
  const isWatched = watchlist?.some((item) => item.barcode === barcode);

  const toggleWatch = useMutation({
    mutationFn: () => isWatched ? api.watchlistRemove(barcode as string) : api.watchlistAdd(barcode as string),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const submitReport = async () => {
    setReportMessage("");
    try {
      await api.submitReport(barcode as string, reportReason);
      setReportMessage("Thanks — our team will review the report.");
      setReportReason("");
      setTimeout(() => setReportOpen(false), 1400);
    } catch (e) {
      setReportMessage((e as Error).message);
    }
  };

  if (isLoading || !product) {
    return (
      <View style={[styles.center, { paddingTop: insets.top }]} testID="product-loading">
        {error ? (
          <>
            <Text style={styles.errorText}>{(error as Error).message}</Text>
            <Pressable onPress={() => router.back()} style={styles.smallButton}>
              <Text style={styles.smallButtonText}>Back</Text>
            </Pressable>
          </>
        ) : (
          <>
            <ActivityIndicator color={colors.brandPrimary} size="large" />
            <Text style={styles.muted}>Analyzing ingredients…</Text>
          </>
        )}
      </View>
    );
  }

  const tone = scoreColor(product.overall_health_score, colors);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.topActions}>
          <Pressable testID="product-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/(tabs)"))} style={styles.backRow}>
            <Ionicons name="arrow-back" size={21} color={colors.onSurface} />
            <Text style={styles.backText}>Back</Text>
          </Pressable>
          <View style={styles.rightActions}>
            {entitlement?.registered ? (
              <Pressable
                testID="product-watch"
                onPress={() => toggleWatch.mutate()}
                style={styles.roundButton}
                accessibilityRole="button"
                accessibilityLabel={isWatched ? "Remove from watchlist" : "Save to watchlist"}
              >
                <Ionicons name={isWatched ? "heart" : "heart-outline"} size={20} color={isWatched ? colors.error : colors.onSurface} />
              </Pressable>
            ) : null}
            <Pressable
              testID="product-report"
              onPress={() => setReportOpen(true)}
              style={styles.roundButton}
              accessibilityRole="button"
              accessibilityLabel="Report inaccurate info"
            >
              <Ionicons name="flag-outline" size={19} color={colors.onSurface} />
            </Pressable>
          </View>
        </View>

        <View style={styles.hero}>
          <View style={styles.artwork}>
            {product.image_url ? (
              <Image source={{ uri: product.image_url }} style={styles.artworkImage} contentFit="cover" />
            ) : (
              <Ionicons
                name={product.category === "food" ? "nutrition" : "flask"}
                size={46}
                color={colors.brandPrimary}
              />
            )}
          </View>
          <Text style={styles.brand} testID="product-brand">{product.brand}</Text>
          <Text style={styles.name} testID="product-name">{product.name}</Text>
          <Text style={styles.muted}>{product.serving_size} · {product.category.replace("_", " ")}</Text>
          <View style={styles.badgeRow}>
            <View style={styles.badge}>
              <Ionicons name="leaf" size={13} color={colors.success} />
              <Text style={styles.badgeText}>
                {product.dietary_type === "not_applicable" ? "Personal care" : product.dietary_type}
              </Text>
            </View>
            <View style={styles.badge}>
              <Ionicons name="location-outline" size={13} color={colors.info} />
              <Text style={styles.badgeText}>{product.origin_country}</Text>
            </View>
            <View style={styles.badge}>
              <Ionicons name="calendar-outline" size={13} color={colors.muted} />
              <Text style={styles.badgeText}>Since {product.first_detected_year}</Text>
            </View>
          </View>
        </View>

        <View style={styles.scoreCard} testID="score-card">
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>HOLISTIC HEALTH SCORE</Text>
            <Text style={[styles.scoreNumber, { color: tone }]} testID="score-value">
              {Math.round(product.overall_health_score)}
            </Text>
            <Text style={styles.muted}>{scoreLabel(product.overall_health_score)} · out of 100</Text>
          </View>
          <View style={[styles.ring, { borderColor: tone }]}>
            <Text style={[styles.ringNumber, { color: tone }]} testID="match-value">
              {product.personal_match}%
            </Text>
            <Text style={styles.ringLabel}>match</Text>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Why this score?</Text>
          <Text style={styles.body}>
            {product.description} Our index weighs every listed ingredient and lower-scoring items are penalized more strongly.
          </Text>
          <RegulatoryBadges badges={product.badges} />
          <Text style={styles.disclaimer}>
            Date of first appearance is estimated based on global web registry logs and retail listings. Analysis is informational, not medical advice.
          </Text>
        </View>

        {product.nutrition_per_100g ? (
          <NutritionCard nutrition={product.nutrition_per_100g} servingSize={product.serving_size} />
        ) : null}

        <PriceBenchmark product={product} />

        <View style={styles.rowBetween}>
          <Text style={styles.sectionTitle}>Ingredient breakdown</Text>
          <Text style={styles.muted}>{product.ingredients.length} listed</Text>
        </View>
        {product.ingredients.map((ingredient) => (
          <Pressable
            key={ingredient.name}
            testID={`ingredient-row-${ingredient.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            onPress={() => setSelected(ingredient)}
            style={styles.ingredientRow}
          >
            <View style={[styles.scoreDot, { backgroundColor: scoreColor(ingredient.score, colors) }]} />
            <View style={styles.ingredientCopy}>
              <Text style={styles.ingredientName}>{ingredient.name}</Text>
              <Text style={styles.muted}>{ingredient.function}</Text>
            </View>
            <Text style={[styles.ingredientScore, { color: scoreColor(ingredient.score, colors) }]}>
              {ingredient.score}
            </Text>
            <Ionicons name="chevron-forward" size={17} color={colors.muted} />
          </Pressable>
        ))}

        <PriceComparison barcode={product.barcode} />

        <BetterForYou barcode={barcode as string} />

        <Pressable
          testID="product-contribute"
          onPress={() => router.push({ pathname: "/contribute/[barcode]", params: { barcode: product.barcode } })}
          style={styles.outlineButton}
        >
          <Ionicons name="add-circle-outline" size={19} color={colors.brandPrimary} />
          <Text style={styles.outlineText}>Contribute a correction</Text>
        </Pressable>
      </ScrollView>
      <IngredientSheet ingredient={selected} onClose={() => setSelected(null)} />
      {reportOpen ? (
        <View style={styles.reportBackdrop}>
          <Pressable style={styles.reportDismiss} onPress={() => setReportOpen(false)} />
          <View style={styles.reportSheet}>
            <View style={styles.reportHandle} />
            <Text style={styles.reportTitle}>Report inaccurate info</Text>
            <Text style={styles.reportBody}>
              Tell us what looks wrong — outdated ingredients, wrong nutrition, misleading badges, etc.
            </Text>
            <TextInput
              testID="report-reason"
              value={reportReason}
              onChangeText={setReportReason}
              placeholder="What should we double-check?"
              placeholderTextColor={colors.muted}
              multiline
              style={styles.reportInput}
            />
            {reportMessage ? <Text style={styles.body}>{reportMessage}</Text> : null}
            <Pressable
              testID="report-submit"
              onPress={submitReport}
              disabled={reportReason.trim().length < 5}
              style={[styles.reportPrimary, reportReason.trim().length < 5 && styles.reportDisabled]}
            >
              <Text style={styles.reportPrimaryText}>Submit report</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  scroll: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 14, backgroundColor: colors.surface },
  topActions: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  rightActions: { flexDirection: "row", gap: 10, alignItems: "center" },
  roundButton: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  backRow: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 44 },
  backText: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
  reportBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(17,19,17,0.36)", justifyContent: "flex-end", zIndex: 30 },
  reportDismiss: { flex: 1 },
  reportSheet: { backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 22, paddingBottom: 32 },
  reportHandle: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: colors.borderStrong, marginBottom: 16 },
  reportTitle: { color: colors.onSurface, fontSize: 20, fontWeight: "800" },
  reportBody: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21, marginTop: 6, marginBottom: 14 },
  reportInput: { minHeight: 100, borderRadius: 14, backgroundColor: colors.surfaceTertiary, padding: 14, color: colors.onSurface, fontSize: 15, textAlignVertical: "top" },
  reportPrimary: { minHeight: 48, borderRadius: 16, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", marginTop: 16 },
  reportPrimaryText: { color: colors.onBrandPrimary, fontSize: 15, fontWeight: "800" },
  reportDisabled: { opacity: 0.5 },
  hero: { alignItems: "center", paddingBottom: 22 },
  artwork: { width: 112, height: 112, borderRadius: 32, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginBottom: 16, overflow: "hidden" },
  artworkImage: { width: "100%", height: "100%" },
  brand: { color: colors.brandPrimary, fontSize: 13, fontWeight: "800", letterSpacing: 0.6 },
  name: { color: colors.onSurface, fontSize: 26, fontWeight: "800", textAlign: "center", marginTop: 5 },
  badgeRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 8, marginTop: 14 },
  badge: { backgroundColor: colors.surfaceSecondary, borderRadius: 18, paddingHorizontal: 11, paddingVertical: 8, flexDirection: "row", gap: 5, alignItems: "center" },
  badgeText: { color: colors.onSurfaceSecondary, fontSize: 12, fontWeight: "700" },
  scoreCard: { borderRadius: 22, backgroundColor: colors.surfaceSecondary, padding: 20, flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 14 },
  label: { color: colors.muted, fontSize: 11, fontWeight: "800", letterSpacing: 0.8 },
  scoreNumber: { fontSize: 45, fontWeight: "800", marginTop: 3 },
  ring: { width: 82, height: 82, borderRadius: 41, borderWidth: 5, alignItems: "center", justifyContent: "center", marginLeft: 16 },
  ringNumber: { fontSize: 20, fontWeight: "800" },
  ringLabel: { color: colors.muted, fontSize: 11 },
  card: { borderRadius: 20, backgroundColor: colors.surfaceSecondary, padding: 18, marginBottom: 18 },
  cardTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800", marginBottom: 7 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21 },
  disclaimer: { color: colors.muted, fontSize: 12, lineHeight: 17, marginTop: 12, fontStyle: "italic" },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 4 },
  sectionTitle: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  muted: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  ingredientRow: { minHeight: 68, flexDirection: "row", alignItems: "center", borderBottomWidth: 1, borderBottomColor: colors.divider, gap: 11 },
  scoreDot: { width: 10, height: 10, borderRadius: 5 },
  ingredientCopy: { flex: 1 },
  ingredientName: { color: colors.onSurface, fontSize: 15, fontWeight: "700" },
  ingredientScore: { fontWeight: "800", fontSize: 17 },
  retailerRow: { minHeight: 68, flexDirection: "row", alignItems: "center", borderBottomWidth: 1, borderBottomColor: colors.divider, gap: 11 },
  retailerIcon: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  retailerCopy: { flex: 1 },
  price: { color: colors.onSurface, fontSize: 15, fontWeight: "800" },
  outlineButton: { minHeight: 48, borderRadius: 16, borderWidth: 1, borderColor: colors.brandPrimary, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginTop: 22 },
  outlineText: { color: colors.brandPrimary, fontSize: 14, fontWeight: "800" },
  errorText: { color: colors.error, fontSize: 14, textAlign: "center", paddingHorizontal: 24 },
  smallButton: { minHeight: 44, borderRadius: 14, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center", paddingHorizontal: 16, marginTop: 10 },
  smallButtonText: { color: colors.onBrandPrimary, fontSize: 13, fontWeight: "800" },
}));

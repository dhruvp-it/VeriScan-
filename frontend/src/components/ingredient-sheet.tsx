import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Ingredient } from "@/src/lib/api";
import { scoreColor, scoreLabel } from "@/src/lib/scoring";
import { makeStyles, useTheme } from "@/src/theme";

type Props = { ingredient: Ingredient | null; onClose: () => void };

export function IngredientSheet({ ingredient, onClose }: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  if (!ingredient) return null;
  const tone = scoreColor(ingredient.score, colors);
  return (
    <View style={styles.backdrop} testID="ingredient-sheet">
      <Pressable style={styles.dismiss} onPress={onClose} testID="ingredient-sheet-dismiss" />
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <View style={styles.headerRow}>
          <Text style={styles.title}>{ingredient.name}</Text>
          <Pressable
            onPress={onClose}
            testID="ingredient-sheet-close"
            accessibilityRole="button"
            accessibilityLabel="Close ingredient details"
            style={styles.closeButton}
          >
            <Ionicons name="close" size={20} color={colors.onSurface} />
          </Pressable>
        </View>
        <View style={styles.scoreChip}>
          <View style={[styles.scoreDot, { backgroundColor: tone }]} />
          <Text style={[styles.scoreText, { color: tone }]}>{ingredient.score}/100 · {scoreLabel(ingredient.score)}</Text>
        </View>
        <Text style={styles.functionText}>{ingredient.function}</Text>
        <Text style={styles.sectionTitle}>Bodily impact</Text>
        <Text style={styles.body}>{ingredient.effect}</Text>
        <Text style={styles.sectionTitle}>Regulatory context</Text>
        <Text style={styles.body}>
          Check the current FDA, EU CosIng, and FSSAI guidance for your region. Formulas and permitted uses can change.
        </Text>
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(17,19,17,0.36)", justifyContent: "flex-end", zIndex: 30 },
  dismiss: { flex: 1 },
  sheet: { backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 22, paddingBottom: 32 },
  handle: { alignSelf: "center", width: 44, height: 5, borderRadius: 3, backgroundColor: colors.borderStrong, marginBottom: 18 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  title: { color: colors.onSurface, fontSize: 22, fontWeight: "800", flex: 1 },
  closeButton: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  scoreChip: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 12 },
  scoreDot: { width: 12, height: 12, borderRadius: 6 },
  scoreText: { fontSize: 14, fontWeight: "800" },
  functionText: { color: colors.brandPrimary, fontSize: 13, fontWeight: "700", marginTop: 8 },
  sectionTitle: { color: colors.onSurface, fontSize: 16, fontWeight: "800", marginTop: 22, marginBottom: 6 },
  body: { color: colors.onSurfaceSecondary, fontSize: 14, lineHeight: 21 },
}));

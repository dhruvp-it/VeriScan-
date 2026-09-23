import { StyleSheet, Text, View } from "react-native";

import { Nutrition } from "@/src/lib/api";
import { makeStyles } from "@/src/theme";

type Props = { nutrition: Nutrition; servingSize?: string };

const ROWS: { key: keyof Nutrition; label: string; unit: string }[] = [
  { key: "energy_kcal", label: "Energy", unit: "kcal" },
  { key: "protein_g", label: "Protein", unit: "g" },
  { key: "carbohydrates_g", label: "Carbohydrates", unit: "g" },
  { key: "sugars_g", label: "of which sugars", unit: "g" },
  { key: "fat_g", label: "Fat", unit: "g" },
  { key: "saturated_fat_g", label: "of which saturated", unit: "g" },
  { key: "fiber_g", label: "Fiber", unit: "g" },
  { key: "salt_g", label: "Salt", unit: "g" },
];

export function NutritionCard({ nutrition, servingSize }: Props) {
  const styles = useStyles();
  const filled = ROWS.filter((row) => nutrition[row.key] != null);
  if (filled.length === 0) return null;
  return (
    <View style={styles.card} testID="nutrition-card">
      <View style={styles.header}>
        <Text style={styles.title}>Nutrition per 100 g</Text>
        {servingSize ? <Text style={styles.serving}>Serving · {servingSize}</Text> : null}
      </View>
      {filled.map((row, index) => (
        <View key={row.key} style={[styles.row, index === filled.length - 1 && styles.rowLast]}>
          <Text style={styles.label}>{row.label}</Text>
          <Text style={styles.value}>{nutrition[row.key]} {row.unit}</Text>
        </View>
      ))}
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  card: { borderRadius: 20, backgroundColor: colors.surfaceSecondary, padding: 18, marginBottom: 18 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  title: { color: colors.onSurface, fontSize: 17, fontWeight: "800" },
  serving: { color: colors.muted, fontSize: 12, fontWeight: "600" },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider },
  rowLast: { borderBottomWidth: 0 },
  label: { color: colors.onSurfaceSecondary, fontSize: 14 },
  value: { color: colors.onSurface, fontSize: 14, fontWeight: "700" },
}));

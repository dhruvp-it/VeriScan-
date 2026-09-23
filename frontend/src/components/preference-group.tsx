import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { makeStyles, useTheme } from "@/src/theme";

type Props = {
  title: string;
  options: readonly string[];
  selected: string[];
  onToggle: (value: string) => void;
};

export function PreferenceGroup({ title, options, selected, onToggle }: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  return (
    <View style={styles.group} testID={`pref-group-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.pills}>
        {options.map((option) => {
          const isSelected = selected.includes(option);
          return (
            <Pressable
              key={option}
              onPress={() => onToggle(option)}
              testID={`pref-pill-${option.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
              accessibilityRole="button"
              accessibilityState={{ selected: isSelected }}
              style={[styles.pill, isSelected && styles.pillSelected]}
            >
              <Text style={[styles.pillText, isSelected && styles.pillTextSelected]}>{option}</Text>
              {isSelected && <Ionicons name="checkmark" size={15} color={colors.onBrandTertiary} />}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  group: { marginBottom: 28 },
  title: { color: colors.onSurface, fontSize: 18, fontWeight: "700" },
  pills: { flexDirection: "row", flexWrap: "wrap", gap: 9, marginTop: 13 },
  pill: {
    minHeight: 44, borderRadius: 24, borderWidth: 1, borderColor: colors.borderStrong,
    paddingHorizontal: 14, alignItems: "center", justifyContent: "center",
    flexDirection: "row", gap: 6, backgroundColor: colors.surface,
  },
  pillSelected: { backgroundColor: colors.brandTertiary, borderColor: colors.brandSecondary },
  pillText: { color: colors.onSurfaceSecondary, fontSize: 14, fontWeight: "600" },
  pillTextSelected: { color: colors.onBrandTertiary },
}));

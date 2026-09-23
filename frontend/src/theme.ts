import { useMemo } from "react";
import { Appearance, StyleSheet, useColorScheme } from "react-native";

export type ColorScheme = "light" | "dark";

const light = {
  surface: "#FDFCFA",
  onSurface: "#1A1C19",
  surfaceSecondary: "#F4F1EA",
  onSurfaceSecondary: "#2C302D",
  surfaceTertiary: "#EAE5DC",
  onSurfaceTertiary: "#4A4F4C",
  surfaceInverse: "#111311",
  onSurfaceInverse: "#FDFCFA",
  muted: "#707873",
  brand: "#2E7D32",
  onBrand: "#FFFFFF",
  brandPrimary: "#2E7D32",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#7CB342",
  onBrandSecondary: "#111311",
  brandTertiary: "#E8F5E9",
  onBrandTertiary: "#1B5E20",
  success: "#2E7D32",
  onSuccess: "#FFFFFF",
  warning: "#FB8C00",
  onWarning: "#FFFFFF",
  yellow: "#FDD835",
  onYellow: "#1A1C19",
  error: "#E53935",
  onError: "#FFFFFF",
  info: "#0288D1",
  onInfo: "#FFFFFF",
  border: "#E2DBD0",
  borderStrong: "#C8BEB0",
  divider: "#EFECE6",
};

export type ThemeColors = typeof light;
export const defaultScheme = "light" satisfies ColorScheme;
export const themes: { light: ThemeColors; dark?: ThemeColors } = { light };

export function setColorScheme(scheme: ColorScheme | null) {
  Appearance.setColorScheme?.(scheme ?? "unspecified");
}

setColorScheme(themes.dark ? null : defaultScheme);

export function useTheme(): { scheme: ColorScheme; colors: ThemeColors } {
  const system = useColorScheme();
  const scheme: ColorScheme = system && themes[system] ? system : defaultScheme;
  return { scheme, colors: themes[scheme] ?? themes.light };
}

export function makeStyles<T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  factory: (colors: ThemeColors) => T & StyleSheet.NamedStyles<any>,
): () => T {
  return function useStyles(): T {
    const { colors } = useTheme();
    return useMemo(() => StyleSheet.create(factory(colors)), [colors]);
  };
}
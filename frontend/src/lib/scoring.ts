import { ThemeColors } from "@/src/theme";

/** Map a 0-100 safety score to the VeriScan 5-tier color spectrum. */
export function scoreColor(score: number, colors: ThemeColors): string {
  if (score <= 20) return colors.error;
  if (score <= 40) return colors.warning;
  if (score <= 60) return colors.yellow;
  if (score <= 80) return colors.brandSecondary;
  return colors.success;
}

export function scoreLabel(score: number): string {
  if (score <= 20) return "Avoid";
  if (score <= 40) return "High concern";
  if (score <= 60) return "Moderation";
  if (score <= 80) return "Safe";
  return "Bio-beneficial";
}

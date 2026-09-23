export const DIETARY_OPTIONS = [
  "Vegan", "Vegetarian", "Pescatarian", "Whole foods", "Keto", "High protein", "Halal", "Jain",
] as const;
export const TARGET_OPTIONS = [
  "Clean eating", "Low sugar", "Low carb", "Low sodium", "Gut health", "Heart health",
  "Weight management", "Energy & focus",
] as const;
export const SENSITIVITY_OPTIONS = [
  "No additives", "Paraben-free", "Sulfate-free", "Fragrance-free", "Cruelty-free",
  "Nut-free", "Dairy-free", "Gluten-free", "Soy-free", "Palm oil free",
] as const;

export type Preferences = {
  dietary: string[];
  targets: string[];
  sensitivities: string[];
};

export const emptyPreferences: Preferences = { dietary: [], targets: [], sensitivities: [] };

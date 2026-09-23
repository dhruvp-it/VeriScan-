export const DIETARY_OPTIONS = ["Vegan", "Vegetarian", "Pescatarian", "Whole foods"] as const;
export const TARGET_OPTIONS = ["Clean eating", "Low sugar", "Low carb", "Gut health", "Heart health"] as const;
export const SENSITIVITY_OPTIONS = [
  "No additives", "Paraben-free", "Fragrance-free", "Cruelty-free", "Nut-free", "Gluten-free",
] as const;

export type Preferences = {
  dietary: string[];
  targets: string[];
  sensitivities: string[];
};

export const emptyPreferences: Preferences = { dietary: [], targets: [], sensitivities: [] };

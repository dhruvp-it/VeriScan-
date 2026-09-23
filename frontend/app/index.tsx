import { Redirect } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { makeStyles, useTheme } from "@/src/theme";
import { storage } from "@/src/utils/storage";

export default function IndexRoute() {
  const styles = useStyles();
  const { colors } = useTheme();
  const [status, setStatus] = useState<"loading" | "onboard" | "ready">("loading");

  useEffect(() => {
    (async () => {
      const done = await storage.getItem("veriscan_onboarded", false);
      setStatus(done ? "ready" : "onboard");
    })();
  }, []);

  if (status === "loading") {
    return (
      <View style={styles.screen} testID="splash">
        <ActivityIndicator color={colors.brandPrimary} size="large" />
        <Text style={styles.text}>Preparing your clean scan</Text>
      </View>
    );
  }
  if (status === "onboard") return <Redirect href="/onboarding" />;
  return <Redirect href="/(tabs)" />;
}

const useStyles = makeStyles((colors) => StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.surface, alignItems: "center", justifyContent: "center", gap: 16 },
  text: { color: colors.muted, fontSize: 15 },
}));

import { Stack } from "expo-router";
import { colors, fonts } from "@/lib/theme";

export default function AppLayout() {
  return (
    <Stack
      screenOptions={{
        headerShadowVisible: false,
        headerStyle: { backgroundColor: colors.white },
        headerTintColor: colors.ink900,
        headerTitleStyle: { fontFamily: fonts.display, fontSize: 17 },
        headerLargeTitleStyle: { fontFamily: fonts.display },
        headerBackButtonDisplayMode: "minimal",
        contentStyle: { backgroundColor: colors.white },
      }}
    >
      <Stack.Screen name="index" options={{ title: "Your cases" }} />
      <Stack.Screen name="cases/[id]" options={{ title: "Case" }} />
      <Stack.Screen
        name="scan"
        options={{ title: "Karen found money", presentation: "modal" }}
      />
    </Stack>
  );
}

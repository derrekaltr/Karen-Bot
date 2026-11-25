/**
 * Karen palette — mirrors apps/web/src/app/globals.css. Derived from the
 * mascot: bobble red, bob blonde, face blue, thick black outlines on white.
 * Money green is reserved for recovered dollars.
 */
export const colors = {
  accent50: "#fef1ef",
  accent100: "#fbdcd8",
  accent500: "#e23b30",
  accent600: "#c92f25",
  accent700: "#a5261e",
  bob100: "#faefd4",
  bob400: "#f0ce8c",
  bob600: "#d9a33f",
  face100: "#eaf5fc",
  face300: "#d8ecfa",
  money100: "#dff4e6",
  money600: "#17854b",
  money700: "#116a3c",
  ink900: "#000000",
  ink600: "#44443e",
  ink400: "#8a8a82",
  white: "#ffffff",
  red50: "#fef2f2",
  red700: "#b91c1c",
} as const;

export const fonts = {
  regular: "Archivo_400Regular",
  medium: "Archivo_500Medium",
  semibold: "Archivo_600SemiBold",
  bold: "Archivo_700Bold",
  display: "ArchivoBlack_400Regular",
} as const;

/** The signature "sticker" look: thick black border + hard offset shadow. */
export const sticker = {
  borderWidth: 2,
  borderColor: colors.ink900,
  borderRadius: 16,
  shadowColor: colors.ink900,
  shadowOffset: { width: 4, height: 4 },
  shadowOpacity: 1,
  shadowRadius: 0,
  elevation: 4,
} as const;

import { ClerkProvider } from "@clerk/nextjs";
import { ClerkTokenBridge } from "@/components/ClerkTokenBridge";
import type { Metadata } from "next";
import { Archivo, Archivo_Black } from "next/font/google";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-archivo",
});

const archivoBlack = Archivo_Black({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-archivo-black",
});

export const metadata: Metadata = {
  title: "KarenBot — They owe you. Karen collects.",
  description:
    "KarenBot negotiates with customer service on your behalf, so you get refunds and compensation without the hold music.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${archivo.variable} ${archivoBlack.variable}`}>
      <body className="min-h-dvh">
        <ClerkProvider
          appearance={{
            variables: {
              colorPrimary: "#e23b30",
              colorForeground: "#000000",
              borderRadius: "12px",
              fontFamily:
                "var(--font-archivo), ui-sans-serif, system-ui, sans-serif",
            },
            elements: {
              cardBox:
                "rounded-2xl border-2 border-black shadow-[6px_6px_0_0_#000]",
              card: "rounded-2xl",
              formButtonPrimary:
                "rounded-xl border-2 border-black bg-accent-500 text-white shadow-[3px_3px_0_0_#000] hover:bg-accent-600",
              socialButtonsBlockButton:
                "rounded-xl border-2 border-black bg-white hover:bg-face-100",
              formFieldInput: "rounded-xl border-2 border-black",
            },
          }}
          localization={{
            signIn: {
              start: {
                title: "Sign in to KarenBot",
                subtitle: "Karen's ready when you are.",
              },
            },
            signUp: {
              start: {
                title: "Create your KarenBot account",
                subtitle: "They owe you. Let's go get it.",
              },
            },
          }}
        >
          <ClerkTokenBridge />
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}

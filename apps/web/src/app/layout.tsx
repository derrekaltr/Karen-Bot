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
        <ClerkProvider>
          <ClerkTokenBridge />
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}

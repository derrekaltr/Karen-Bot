import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KarenBot — Stop fighting customer service",
  description:
    "KarenBot negotiates with customer service on your behalf, so you get refunds and compensation without the hold music.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}

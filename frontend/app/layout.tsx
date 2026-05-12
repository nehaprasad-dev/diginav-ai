import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DigiNav AI",
  description:
    "Autonomous regulatory compliance agent for Indian MSMEs and startups.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}

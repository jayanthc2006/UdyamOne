import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UdyamOne | A simpler digital journey for MSMEs",
  description: "Discover, compare and onboard the digital services your business needs with UdyamOne.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}

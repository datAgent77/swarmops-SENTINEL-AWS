import "./styles.css";

export const metadata = {
  title: "SwarmOps — Living AI Workforce",
  description: "Real-time control plane for an autonomous AI workforce under deterministic governance.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import "./styles.css";

export const metadata = {
  title: "Sentinel — AI Security Officer for Ring",
  description: "Ring + Amazon Bedrock, governed by SwarmOps. An AI security officer that understands, follows policy, and asks for human approval.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

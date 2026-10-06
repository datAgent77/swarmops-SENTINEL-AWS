import { redirect } from "next/navigation";

// Sentinel is the product: the root sends everyone straight to the command screen.
export default function Home() {
  redirect("/sentinel");
}

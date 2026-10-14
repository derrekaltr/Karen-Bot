import type { Metadata } from "next";
import { AdminConsole } from "./admin-console";

export const metadata: Metadata = {
  title: "Admin console — KarenBot",
};

export default function AdminPage() {
  return <AdminConsole />;
}

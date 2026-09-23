import type { MetadataRoute } from "next";
import { SERVICE_DESCRIPTION, SERVICE_NAME } from "@/lib/brand";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SERVICE_NAME,
    short_name: SERVICE_NAME,
    description: SERVICE_DESCRIPTION,
    start_url: "/",
    display: "standalone",
    background_color: "#f5f5f7",
    theme_color: "#124532",
  };
}

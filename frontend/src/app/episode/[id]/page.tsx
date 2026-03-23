import { EpisodePageClient } from "@/components/EpisodePageClient";

export default async function EpisodePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EpisodePageClient id={Number(id)} />;
}

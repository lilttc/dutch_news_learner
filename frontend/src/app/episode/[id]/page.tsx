import { getEpisode } from "@/lib/api";
import { EpisodeView } from "@/components/EpisodeView";

export default async function EpisodePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const episode = await getEpisode(Number(id));

  return <EpisodeView episode={episode} />;
}

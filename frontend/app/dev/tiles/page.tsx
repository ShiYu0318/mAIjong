import { TileImage } from "@/components/Hand/TileImage";

const IDS = Array.from({ length: 42 }, (_, i) => i);

export default function TilesPreview() {
  return (
    <main className="p-8">
      <h1 className="font-display text-3xl mb-6">牌張素材</h1>
      <div className="grid grid-cols-9 gap-3 w-fit">
        {IDS.map((id) => (
          <TileImage key={id} id={id} width={60} />
        ))}
        <TileImage id={null} width={60} />
      </div>
    </main>
  );
}

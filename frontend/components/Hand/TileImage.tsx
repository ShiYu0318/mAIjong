"use client";

import { useEffect, useState } from "react";
import { TILE_H, TILE_W, ensureTileFont, tileDataUrl } from "@/lib/tilePainter";
import { tileName } from "@/lib/tiles";

type Props = { id: number | null; width?: number; className?: string; title?: string };

/** DOM tile picture rendered from the shared canvas painter. */
export function TileImage({ id, width = 36, className, title }: Props) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    ensureTileFont().then((font) => {
      if (alive) setSrc(tileDataUrl(id, font));
    });
    return () => {
      alive = false;
    };
  }, [id]);
  const height = (width * TILE_H) / TILE_W;
  const label = id === null ? "蓋牌" : tileName(id);
  return src ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} width={width} height={height} alt={label} title={title ?? label}
      className={className} draggable={false} />
  ) : (
    <span style={{ width, height }} className={`inline-block rounded-md bg-ivory/20 ${className ?? ""}`}
      aria-label={label} />
  );
}

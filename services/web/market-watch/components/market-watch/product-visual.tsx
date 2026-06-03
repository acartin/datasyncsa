"use client";

import { useState } from "react";
import { ImageOff, PackageSearch } from "lucide-react";

function Placeholder({ hasSku }: { hasSku: boolean }) {
  return (
    <div className="flex h-36 w-36 shrink-0 items-center justify-center rounded-md border bg-surface-2 text-muted-foreground">
      {hasSku ? <ImageOff className="h-8 w-8" /> : <PackageSearch className="h-8 w-8" />}
    </div>
  );
}

function SafeImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;

  return (
    <img
      src={src}
      alt={alt}
      className="h-full w-full object-contain"
      onError={() => setFailed(true)}
    />
  );
}

export function ProductVisual({ hasSku, images }: { hasSku: boolean; images: string[] }) {
  const [primaryFailed, setPrimaryFailed] = useState(false);

  if (hasSku && images[0] && !primaryFailed) {
    return (
      <div className="flex h-36 w-36 shrink-0 items-center justify-center overflow-hidden rounded-md border bg-background">
        <img
          src={images[0]}
          alt="Product"
          className="h-full w-full object-contain"
          onError={() => setPrimaryFailed(true)}
        />
      </div>
    );
  }

  if (!hasSku && images.length > 1) {
    return (
      <div className="grid h-36 w-36 shrink-0 grid-cols-2 gap-1 overflow-hidden rounded-md border bg-background p-1">
        {images.map((image) => (
          <div key={image} className="flex items-center justify-center overflow-hidden rounded-sm bg-card">
            <SafeImage src={image} alt="Related product" />
          </div>
        ))}
      </div>
    );
  }

  return <Placeholder hasSku={hasSku} />;
}

import Image from "next/image";
import { cn } from "@/lib/utils";

export function BrandMark({
  full = false,
  className,
  priority = false,
}: {
  full?: boolean;
  className?: string;
  priority?: boolean;
}) {
  return (
    <Image
      src={full ? "/brand/cmai-full.png" : "/brand/cmai-building.png"}
      alt={full ? "CMAI Chiang Mai AI Center" : "CMAI"}
      width={full ? 680 : 306}
      height={full ? 370 : 370}
      priority={priority}
      className={cn("object-contain", className)}
    />
  );
}

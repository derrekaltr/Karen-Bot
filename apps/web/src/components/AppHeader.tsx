import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

export function AppHeader({ right }: { right?: ReactNode }) {
  return (
    <header className="border-b-2 border-black bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
        <Link href="/" className="flex items-center gap-2">
          <Image
            src="/karen.png"
            alt=""
            width={40}
            height={41}
            className="-my-1"
          />
          <span className="font-display text-xl tracking-tight">KarenBot</span>
        </Link>
        {right}
      </div>
    </header>
  );
}

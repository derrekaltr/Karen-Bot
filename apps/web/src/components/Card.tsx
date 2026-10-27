import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`rounded-2xl border-2 border-black bg-white p-6 shadow-[4px_4px_0_0_#000] ${className}`}
    >
      {children}
    </div>
  );
}

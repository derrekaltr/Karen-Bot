import Link from "next/link";
import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger";

const baseClasses =
  "inline-flex min-h-11 items-center justify-center rounded-xl border-2 border-black px-5 py-2.5 text-sm font-bold shadow-[3px_3px_0_0_#000] transition-[transform,box-shadow] hover:translate-x-px hover:translate-y-px hover:shadow-[2px_2px_0_0_#000] active:translate-x-[3px] active:translate-y-[3px] active:shadow-none";

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent-500 text-white hover:bg-accent-600",
  secondary: "bg-white text-ink-900 hover:bg-face-100",
  danger: "bg-white text-accent-600 hover:bg-accent-50",
};

interface ButtonLinkProps {
  href: string;
  variant?: ButtonVariant;
  children: ReactNode;
}

export function ButtonLink({
  href,
  variant = "primary",
  children,
}: ButtonLinkProps) {
  return (
    <Link href={href} className={`${baseClasses} ${variantClasses[variant]}`}>
      {children}
    </Link>
  );
}

interface ButtonProps {
  variant?: ButtonVariant;
  type?: "button" | "submit";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  type = "button",
  disabled,
  onClick,
  className = "",
  children,
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${baseClasses} ${variantClasses[variant]} disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}

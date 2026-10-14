import Link from "next/link";
import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger";

const baseClasses =
  "inline-flex min-h-11 items-center justify-center rounded-lg px-5 py-2.5 text-sm font-semibold transition-colors";

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent-600 text-white hover:bg-accent-700",
  secondary:
    "border border-slate-300 bg-white text-ink-900 hover:border-slate-400 hover:bg-slate-50",
  danger:
    "border border-red-300 bg-white text-red-700 hover:border-red-400 hover:bg-red-50",
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

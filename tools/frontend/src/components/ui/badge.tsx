import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold transition-colors focus:outline-none focus:ring-1 focus:ring-sky-400 font-mono select-none",
  {
    variants: {
      variant: {
        default: "bg-sky-500/20 text-sky-300 border border-sky-500/30",
        secondary: "bg-slate-800 text-slate-300 border border-slate-700",
        destructive: "bg-rose-500/20 text-rose-300 border border-rose-500/30",
        outline: "text-slate-300 border border-slate-700",
        template: "bg-sky-500/20 text-sky-400 border border-sky-500/30",
        ocr: "bg-purple-500/20 text-purple-400 border border-purple-500/30",
        composite: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
        success: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };

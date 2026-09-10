import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold transition-colors focus:outline-none focus:ring-1 focus:ring-slate-700/15 font-mono select-none",
  {
    variants: {
      variant: {
        default: "bg-[#f1f1ee] text-slate-300 border border-[#e3e3df]",
        secondary: "bg-[#f7f7f5] text-slate-400 border border-[#e8e8e4]",
        destructive: "bg-[#fff2f1] text-rose-300 border border-[#f2d7d5]",
        outline: "text-slate-400 border border-[#dfdfdb] bg-white",
        template: "bg-[#f2f4f7] text-[#4c5d70] border border-[#e0e5ea]",
        ocr: "bg-[#f7f1fb] text-[#77528c] border border-[#eadff0]",
        composite: "bg-[#fff8e9] text-amber-300 border border-[#f2e2b9]",
        success: "bg-[#edf8f1] text-emerald-300 border border-[#d8eddf]",
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

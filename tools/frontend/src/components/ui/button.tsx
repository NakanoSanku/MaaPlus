import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-700/15 disabled:pointer-events-none disabled:opacity-45 select-none cursor-pointer",
  {
    variants: {
      variant: {
        default: "border border-[#1b1b1a] bg-[#1b1b1a] text-white shadow-[0_1px_2px_rgba(0,0,0,0.12)] hover:bg-[#30302e] hover:border-[#30302e]",
        destructive: "border border-rose-500 bg-rose-500 text-white shadow-sm hover:bg-rose-600",
        outline: "border border-[#dfdfdb] bg-white text-slate-300 shadow-[0_1px_2px_rgba(20,20,18,0.03)] hover:bg-[#f7f7f5] hover:border-[#d1d1cc]",
        secondary: "border border-[#e7e7e3] bg-[#f5f5f2] text-slate-200 hover:bg-[#ecece8]",
        ghost: "border border-transparent text-slate-400 hover:bg-[#f3f3f0] hover:text-slate-100",
        link: "text-slate-200 underline-offset-4 hover:underline",
        success: "border border-emerald-500 bg-emerald-500 text-white shadow-sm hover:bg-emerald-600",
      },
      size: {
        default: "h-8 px-3 py-1.5",
        sm: "h-7 rounded-lg px-2.5 text-[11px]",
        lg: "h-9 rounded-lg px-4 text-sm",
        icon: "h-7 w-7 rounded-lg",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };

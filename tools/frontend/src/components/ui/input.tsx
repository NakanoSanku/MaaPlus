import * as React from "react";
import { cn } from "../../lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-8 w-full rounded-lg border border-[#e1e1dd] bg-white px-2.5 py-1 text-xs text-slate-100 placeholder:text-slate-600 shadow-[0_1px_2px_rgba(20,20,18,0.02)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-700/10 focus-visible:border-[#c8c8c2] disabled:cursor-not-allowed disabled:opacity-50 transition-all",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };

import * as React from 'react';
import { X } from 'lucide-react';

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function Dialog({ open, onOpenChange, title, description, children }: DialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-[1px] transition-opacity"
        onClick={() => onOpenChange(false)}
      />
      <div className="relative z-50 w-full max-w-md rounded-xl border border-[#dfdfda] bg-white p-5 text-[#292927] shadow-[0_18px_55px_rgba(30,30,28,0.16)] animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between gap-4 border-b border-[#eeeeea] pb-3">
          <div>
            <h3 className="text-[13px] font-semibold text-[#242421]">{title}</h3>
            {description && <p className="mt-1 text-[10px] leading-4 text-[#85857d]">{description}</p>}
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="rounded-md p-1.5 text-[#8d8d86] transition-colors hover:bg-[#f4f4f1] hover:text-[#292927]"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="pt-4">{children}</div>
      </div>
    </div>
  );
}

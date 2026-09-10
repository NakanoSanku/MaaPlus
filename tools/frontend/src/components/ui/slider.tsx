import * as React from 'react';
import { cn } from '../../lib/utils';

interface SliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  className?: string;
  label?: string;
  unit?: string;
}

export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  className,
  label,
  unit = '',
}: SliderProps) {
  return (
    <div className={cn("flex flex-col space-y-1.5", className)}>
      {(label !== undefined || unit) && (
        <div className="flex justify-between items-center text-xs">
          {label && <span className="text-slate-400 font-medium">{label}</span>}
          <span className="text-sky-400 font-mono font-semibold">
            {value}
            {unit}
          </span>
        </div>
      )}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-500 focus:outline-none"
      />
    </div>
  );
}

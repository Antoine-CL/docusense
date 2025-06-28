import React from 'react';

interface RetentionSliderProps {
  days: number;
  onChange: (days: number) => void;
}

export default function RetentionSlider({ days, onChange }: RetentionSliderProps) {
  return (
    <div>
      <label className="block font-semibold mb-1">
        Delete embeddings {days} days after source file deleted ({days}d)
      </label>
      <input 
        type="range" 
        min={0} 
        max={365} 
        value={days}
        className="w-full"
        onChange={e => onChange(Number(e.target.value))}
      />
      <div className="flex justify-between text-sm text-gray-500 mt-1">
        <span>0 days</span>
        <span>365 days</span>
      </div>
    </div>
  );
} 
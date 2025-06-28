import React from 'react';

interface RegionSelectProps {
  value: string;
  onChange: (region: string) => void;
}

const regions = ["canadacentral", "eastus", "westeurope"];

export default function RegionSelect({ value, onChange }: RegionSelectProps) {
  return (
    <div>
      <label className="block font-semibold mb-1">Data residency region</label>
      <select 
        className="border p-2 rounded" 
        value={value} 
        onChange={e => onChange(e.target.value)}
      >
        {regions.map(r => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
    </div>
  );
} 
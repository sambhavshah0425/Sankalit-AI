import React from 'react';

interface BrandMarkProps {
  size?: number;
  className?: string;
  variant?: 'mark' | 'full' | 'tile';
}

/**
 * BrandMark Component
 * Conforms strictly to SKL-BRD-SG-001 Rev 05:
 * - Mark: Three overlapping horizontal circles (Amber #F7C05A, Orange #F5A623, Silver #C8C8C8)
 * - Dot: Deep Orange #E8820C / Sankalit Orange #F5A623
 * - Logo Plate: Authentic white / light-grey (#F5F5F5) surface with required clear space
 */
export const BrandMark: React.FC<BrandMarkProps> = ({
  size = 28,
  className = '',
  variant = 'mark',
}) => {
  // Option A / Full: Official Horizontal Lockup from Style Guide Rev 05 (Light Grey background)
  if (variant === 'full') {
    return (
      <div
        className={`inline-flex items-center justify-center rounded-md bg-[#F5F5F5] border border-[#C8C8C8]/40 px-2 py-0.5 shadow-sm select-none ${className}`}
        style={{ height: Math.max(size, 28) }}
      >
        <img
          src="/sankalit-logo-lightgrey.png"
          alt="Sankalit Consultant"
          className="h-full w-auto object-contain max-h-[30px]"
          loading="eager"
        />
      </div>
    );
  }

  // Authentic white / light-grey tile with clear space
  if (variant === 'tile') {
    return (
      <div
        className={`inline-flex items-center justify-center rounded-lg bg-[#FFFFFF] border border-[#C8C8C8]/50 p-1.5 shadow-sm select-none ${className}`}
        style={{ width: size, height: size }}
      >
        <BrandMark size={Math.round(size * 0.55)} variant="mark" />
      </div>
    );
  }

  // Variant: 'mark' - Exact vector 3 overlapping circles (Amber, Orange, Silver)
  const width = Math.round(size * 1.8);
  const height = size;

  return (
    <div
      className={`inline-flex items-center justify-center flex-shrink-0 select-none ${className}`}
      style={{ width, height }}
      title="Sankalit"
      aria-label="Sankalit Mark"
    >
      <svg
        width={width}
        height={height}
        viewBox="0 0 54 28"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="overflow-visible"
      >
        {/* Circle 1: Sankalit Amber (#F7C05A) */}
        <circle cx="14" cy="14" r="13" fill="#F7C05A" fillOpacity="0.95" />
        {/* Circle 2: Sankalit Orange (#F5A623) */}
        <circle cx="27" cy="14" r="13" fill="#F5A623" fillOpacity="0.95" />
        {/* Circle 3: Sankalit Silver (#C8C8C8) */}
        <circle cx="40" cy="14" r="13" fill="#C8C8C8" fillOpacity="0.90" />
      </svg>
    </div>
  );
};

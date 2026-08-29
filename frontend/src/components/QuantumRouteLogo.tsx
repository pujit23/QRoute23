import React from 'react';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
  showSubtext?: boolean;
  onClick?: () => void;
}

export const QuantumRouteLogo: React.FC<LogoProps> = ({
  size = 'md',
  onClick
}) => {
  const sizeMap = {
    sm: { icon: 20, text: 'text-base' },
    md: { icon: 24, text: 'text-lg' },
    lg: { icon: 28, text: 'text-xl' }
  };

  const dim = sizeMap[size];

  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center gap-2.5 select-none group transition-opacity hover:opacity-90 ${
        onClick ? 'cursor-pointer' : ''
      }`}
    >
      {/* Hexagonal 6-Node Quantum Graph Glyph (Without outer box) */}
      <div className="flex items-center justify-center shrink-0">
        <svg
          width={dim.icon}
          height={dim.icon}
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Hexagon Outline */}
          <path
            d="M12 2L20 7V17L12 22L4 17V7L12 2Z"
            stroke="#ffb59e"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          {/* 6 Orbital Vertex Nodes */}
          <circle cx="12" cy="2" r="1.5" fill="#ff5719" />
          <circle cx="20" cy="7" r="1.5" fill="#ffb59e" />
          <circle cx="20" cy="17" r="1.5" fill="#ff5719" />
          <circle cx="12" cy="22" r="1.5" fill="#ffb59e" />
          <circle cx="4" cy="17" r="1.5" fill="#ff5719" />
          <circle cx="4" cy="7" r="1.5" fill="#ffb59e" />
          {/* Lightning Bolt Core */}
          <path
            d="M13 6L9 13H14L11 18"
            stroke="#ff5719"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Clean Horizontal Brand Text */}
      <span
        className={`font-bold tracking-tight ${dim.text}`}
        style={{ color: 'var(--color-text-primary)' }}
      >
        Quantum Route
      </span>
    </div>
  );
};

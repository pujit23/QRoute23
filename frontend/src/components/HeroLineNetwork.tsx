import React from 'react';
import { useTheme } from '../context/ThemeContext';

const HeroLineNetwork: React.FC = () => {
  const { theme } = useTheme();
  const isLight = theme === 'light';

  // Light mode: faint watermark (opacity 0.18, soft stop opacities)
  // Dark mode: original dramatic glow (opacity 0.45, bold stop opacities)
  const groupOpacity = isLight ? 0.18 : 0.45;
  const stopOpacity0 = isLight ? 0.4 : 0.9;
  const stopOpacity50 = isLight ? 0.25 : 0.6;
  const stopColor50 = isLight ? '#d9490f' : '#ffb59e';
  const dotFill = isLight ? '#d9490f' : '#ffb59e';
  const dotOpacity = isLight ? 0.4 : 0.7;

  return (
    <svg
      className="pointer-events-none absolute inset-0 w-full h-full"
      viewBox="0 0 1200 500"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="heroLineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ff5719" stopOpacity={stopOpacity0} />
          <stop offset="50%" stopColor={stopColor50} stopOpacity={stopOpacity50} />
          <stop offset="100%" stopColor="#ff5719" stopOpacity="0" />
        </linearGradient>
        <filter id="heroLineGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g stroke="url(#heroLineGrad)" strokeWidth="1.5" fill="none" filter="url(#heroLineGlow)" opacity={groupOpacity}>
        <polyline
          points="820,60 950,220 1090,110"
          strokeDasharray="400"
          strokeDashoffset="400"
        >
          <animate
            attributeName="stroke-dashoffset"
            values="400;0;400"
            dur="8s"
            begin="0s"
            repeatCount="indefinite"
          />
        </polyline>

        <polyline
          points="900,420 1030,300 1180,380"
          strokeDasharray="360"
          strokeDashoffset="360"
        >
          <animate
            attributeName="stroke-dashoffset"
            values="360;0;360"
            dur="7s"
            begin="1.5s"
            repeatCount="indefinite"
          />
        </polyline>

        <polyline
          points="60,120 180,40 260,150"
          strokeDasharray="300"
          strokeDashoffset="300"
        >
          <animate
            attributeName="stroke-dashoffset"
            values="300;0;300"
            dur="9s"
            begin="3s"
            repeatCount="indefinite"
          />
        </polyline>

        <polyline
          points="40,380 150,440 280,360"
          strokeDasharray="320"
          strokeDashoffset="320"
        >
          <animate
            attributeName="stroke-dashoffset"
            values="320;0;320"
            dur="7.5s"
            begin="4.5s"
            repeatCount="indefinite"
          />
        </polyline>
      </g>

      <circle cx="1090" cy="110" r="3" fill={dotFill} opacity={dotOpacity}>
        <animate
          attributeName="opacity"
          values={isLight ? "0.2;0.45;0.2" : "0.3;0.8;0.3"}
          dur="3s"
          repeatCount="indefinite"
        />
      </circle>
      <circle cx="260" cy="150" r="3" fill={dotFill} opacity={dotOpacity}>
        <animate
          attributeName="opacity"
          values={isLight ? "0.2;0.45;0.2" : "0.3;0.8;0.3"}
          dur="3.5s"
          begin="1s"
          repeatCount="indefinite"
        />
      </circle>
    </svg>
  );
};

export default HeroLineNetwork;

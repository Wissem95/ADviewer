interface LogoProps {
  size?: number;
  glow?: boolean;
  className?: string;
}

/**
 * Logo LocalCoder — pastille à gradient cyan→violet→magenta avec une invite
 * de terminal `›_` ciselée. Mark dessinée (pas un glyphe générique).
 */
export function Logo({ size = 28, glow = false, className = "" }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={glow ? { filter: "drop-shadow(0 0 14px rgba(123,108,255,0.55))" } : undefined}
      aria-hidden
    >
      <defs>
        <linearGradient id="lc-grad" x1="6" y1="6" x2="42" y2="42" gradientUnits="userSpaceOnUse">
          <stop stopColor="#34d8e6" />
          <stop offset="0.5" stopColor="#7b6cff" />
          <stop offset="1" stopColor="#ff5fa2" />
        </linearGradient>
      </defs>
      <rect x="4" y="4" width="40" height="40" rx="13" fill="url(#lc-grad)" />
      <path
        d="M17 17.5 L24.5 24 L17 30.5"
        stroke="#0b0d12"
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <rect x="26.5" y="28" width="8.5" height="3.4" rx="1.7" fill="#0b0d12" />
    </svg>
  );
}

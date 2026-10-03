// ecg waveform: baseline → P wave → Q dip → tall R spike → deep S → baseline → T wave → baseline
// shared with app/opengraph-image.tsx; app/icon.svg keeps its own copy (static file)
export const PULSE_PATH =
  "M1.5 13H4Q5.75 8 7.5 13H9L9.75 14.5L11.25 3L12.75 17.5L13.75 13H15Q17.5 6.5 20 13H22.5";

interface Props {
  className?: string;
  size?: number;
}

export default function PulseLogo({ className, size = 20 }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PULSE_PATH} />
    </svg>
  );
}

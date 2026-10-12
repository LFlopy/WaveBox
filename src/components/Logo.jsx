// Один компонент на все экраны, поэтому шрифт и свечение везде одинаковые.
export default function Logo({ className = "" }) {
  return (
    <span
      className={`font-display font-normal leading-none text-mist drop-shadow-[0_0_14px_rgba(139,95,191,0.9)] ${className}`}
    >
      MUSIC
    </span>
  );
}

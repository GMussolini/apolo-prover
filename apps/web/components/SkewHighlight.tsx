export function SkewHighlight({ children }: { children: React.ReactNode }) {
  return (
    <span className="relative inline-block">
      <span
        className="absolute inset-0 bg-ap-blue"
        style={{ transform: "skewX(-5deg)", inset: "-2px 0" }}
        aria-hidden
      />
      <span className="relative z-10 text-ap-black px-1">{children}</span>
    </span>
  );
}

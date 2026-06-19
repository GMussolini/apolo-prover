export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[10px] font-semibold tracking-[0.25em] uppercase text-ap-text-faint">
      {children}
    </p>
  );
}

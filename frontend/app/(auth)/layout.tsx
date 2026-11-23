import {
  CalendarClock,
  FileText,
  Pill,
  ScanLine,
  ShieldCheck,
} from "lucide-react";

export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const features = [
    {
      icon: ScanLine,
      title: "AI digitization",
      text: "Vision model reads prescriptions and extracts every medication.",
    },
    {
      icon: ShieldCheck,
      title: "Safety check",
      text: "Automatic interaction review with severity ratings.",
    },
    {
      icon: CalendarClock,
      title: "Daily schedules",
      text: "Clear medication timing derived from the prescription.",
    },
    {
      icon: FileText,
      title: "Structured records",
      text: "Searchable, exportable prescription archive.",
    },
  ];

  return (
    <div className="bg-background flex min-h-screen">
      {/* Branding panel */}
      <div className="bg-primary text-primary-foreground relative hidden w-1/2 flex-col justify-between overflow-hidden p-10 lg:flex">
        <div className="pointer-events-none absolute inset-0 opacity-[0.07]">
          <div className="absolute -top-24 -left-24 size-96 rounded-full bg-current" />
          <div className="absolute right-[-6rem] bottom-[-6rem] size-[28rem] rounded-full bg-current" />
        </div>
        <div className="relative flex items-center gap-2">
          <div className="bg-primary-foreground text-primary flex size-9 items-center justify-center rounded-lg">
            <Pill className="size-5" />
          </div>
          <span className="text-lg font-semibold tracking-tight">
            Medical Prescription Digitizer
          </span>
        </div>

        <div className="relative max-w-md space-y-8">
          <h1 className="text-3xl font-bold leading-tight tracking-tight">
            From paper prescriptions to structured, searchable records — in
            seconds.
          </h1>
          <ul className="space-y-5">
            {features.map((feature) => (
              <li key={feature.title} className="flex items-start gap-3">
                <div className="bg-primary-foreground/15 mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg">
                  <feature.icon className="size-4" />
                </div>
                <div>
                  <p className="text-sm font-semibold">{feature.title}</p>
                  <p className="text-primary-foreground/70 mt-0.5 text-sm">
                    {feature.text}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-primary-foreground/60 relative text-xs">
          Local-first AI (Ollama · Qwen3-VL) — no prescription data leaves your
          infrastructure.
        </p>
      </div>

      {/* Form panel */}
      <div className="bg-muted/30 flex flex-1 flex-col items-center justify-center gap-6 p-6">
        <div className="flex items-center gap-2 lg:hidden">
          <div className="bg-primary text-primary-foreground flex size-9 items-center justify-center rounded-lg">
            <Pill className="size-5" />
          </div>
          <span className="text-lg font-semibold tracking-tight">
            Medical Prescription Digitizer
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}

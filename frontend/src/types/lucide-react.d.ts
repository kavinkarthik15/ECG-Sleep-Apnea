declare module 'lucide-react' {
  import type * as React from 'react';

  type IconProps = React.SVGProps<SVGSVGElement> & {
    size?: number | string;
    color?: string;
    strokeWidth?: number | string;
  };

  export type LucideIcon = React.ComponentType<IconProps>;

  export const Activity: LucideIcon;
  export const AlertCircle: LucideIcon;
  export const AlertTriangle: LucideIcon;
  export const ArrowDown: LucideIcon;
  export const ArrowLeft: LucideIcon;
  export const ArrowRight: LucideIcon;
  export const BarChart3: LucideIcon;
  export const BookOpen: LucideIcon;
  export const BrainCircuit: LucideIcon;
  export const Check: LucideIcon;
  export const CheckCircle2: LucideIcon;
  export const Circle: LucideIcon;
  export const CircleDashed: LucideIcon;
  export const CircleHelp: LucideIcon;
  export const Clock3: LucideIcon;
  export const Database: LucideIcon;
  export const Download: LucideIcon;
  export const FileText: LucideIcon;
  export const FileUp: LucideIcon;
  export const Filter: LucideIcon;
  export const Gauge: LucideIcon;
  export const HeartPulse: LucideIcon;
  export const Home: LucideIcon;
  export const Info: LucideIcon;
  export const Menu: LucideIcon;
  export const RotateCcw: LucideIcon;
  export const ShieldCheck: LucideIcon;
  export const Sparkles: LucideIcon;
  export const UploadCloud: LucideIcon;
  export const X: LucideIcon;
  export const XCircle: LucideIcon;
}

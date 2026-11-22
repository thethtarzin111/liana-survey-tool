/**
 * The other Liana apps in the header's apps menu. Their addresses differ per
 * environment (testing / staging / production), so they come from Vite settings:
 * VITE_LIANA_MAILER_URL and the others below, set in frontend/.env.development
 * for `npm run dev` and in the build environment for other deployments
 * (see frontend/.env.example). An app without an address says "not available yet".
 */
export type LianaApp = {
  name: string;
  url: string | undefined;
  /** Background of the app icon (design tokens). */
  color: string;
  /** Stroke icon drawn in white on the coloured square. */
  icon: string;
  /** Listed under "Others" in the menu. */
  other?: boolean;
};

type AppEnv = Pick<
  ImportMetaEnv,
  'VITE_LIANA_MAILER_URL' | 'VITE_LIANA_MONITOR_URL' | 'VITE_LIANA_AUTOMATION_URL' | 'VITE_LIANA_ACCOUNT_URL'
>;

const url = (value: string | undefined) => (value && value.trim() ? value.trim() : undefined);

/** The apps, with their addresses from `env` (by default this build's settings). */
export const lianaApps = (env: AppEnv = import.meta.env): LianaApp[] => [
  {
    name: 'LianaMailer',
    url: url(env.VITE_LIANA_MAILER_URL),
    color: 'var(--color-app-mailer)',
    icon: 'M4 6h16v12H4zM4 7l8 6 8-6',
  },
  {
    name: 'LianaMonitor',
    url: url(env.VITE_LIANA_MONITOR_URL),
    color: 'var(--color-app-monitor)',
    icon: 'M4 19V5M4 19h16M8 15l4-4 3 3 5-6',
  },
  {
    name: 'LianaAutomation',
    url: url(env.VITE_LIANA_AUTOMATION_URL),
    color: 'var(--color-brand-dark)',
    icon: 'M5 6h5v5H5zM14 13h5v5h-5zM10 8.5h3a2 2 0 0 1 2 2V13',
  },
  {
    name: 'LianaAccount',
    url: url(env.VITE_LIANA_ACCOUNT_URL),
    color: 'var(--color-brand)',
    icon: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20c.8-3.5 3.6-5.5 7-5.5s6.2 2 7 5.5',
    other: true,
  },
];

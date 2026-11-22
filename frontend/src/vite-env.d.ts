/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Addresses of the other Liana apps for the header's apps menu (see src/config/lianaApps.ts). */
  readonly VITE_LIANA_MAILER_URL?: string;
  readonly VITE_LIANA_MONITOR_URL?: string;
  readonly VITE_LIANA_AUTOMATION_URL?: string;
  readonly VITE_LIANA_ACCOUNT_URL?: string;
}

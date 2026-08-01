/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 显式启用本地 mock 适配器（仅 dev 生效）。默认关闭，设 "true" 才开启。 */
  readonly VITE_USE_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/// <reference types="vite/client" />

declare module "*.png" {
  const src: string;
  export default src;
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}

interface ImportMetaEnv {
  readonly BASE_URL: string;
  readonly VITE_API_PORTAL_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

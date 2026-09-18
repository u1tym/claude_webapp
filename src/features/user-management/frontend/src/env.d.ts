/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}

interface ImportMetaEnv {
  readonly BASE_URL: string;
  readonly VITE_API_USER_MANAGEMENT_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

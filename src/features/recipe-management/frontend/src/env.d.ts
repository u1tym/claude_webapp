/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}

interface ImportMetaEnv {
  readonly BASE_URL: string;
  readonly VITE_API_RECIPE_MANAGEMENT_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

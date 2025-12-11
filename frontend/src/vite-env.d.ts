/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USER_POOL_ID: string
  readonly VITE_USER_POOL_CLIENT_ID: string
  readonly VITE_AWS_REGION: string
  readonly VITE_AGENTCORE_RUNTIME_ARN: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

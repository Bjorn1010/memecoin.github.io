import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    // Pure-function tests must never touch the network. Any test that needs an
    // RPC lives in test/integration and is opt-in via RUN_INTEGRATION=1.
    exclude: ["node_modules/**", "test/integration/**"],
    environment: "node",
  },
});

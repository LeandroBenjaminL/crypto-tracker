// @ts-check
import { defineConfig } from "astro/config";

// https://astro.build/config
export default defineConfig({
  site: "https://LeandroBenjaminL.github.io",
  base: "/crypto-tracker",
  // GitHub Pages sirve archivos estáticos; el fetching es client-side
  output: "static",
});

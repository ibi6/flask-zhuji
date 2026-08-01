/** GitHub Pages SPA：404 回退到 index.html */
import { copyFileSync } from "node:fs";
import { join } from "node:path";

const dist = "dist";
copyFileSync(join(dist, "index.html"), join(dist, "404.html"));
console.log("Copied dist/index.html -> dist/404.html");

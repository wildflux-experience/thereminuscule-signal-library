import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const repoRoot = dirname(siteRoot);
const publicRoot = join(siteRoot, "public");
const libraryPath = join(repoRoot, "library.json");
const publicLibraryPath = join(publicRoot, "library.json");

mkdirSync(publicRoot, { recursive: true });
copyFileSync(libraryPath, publicLibraryPath);

const library = JSON.parse(readFileSync(libraryPath, "utf-8"));

for (const signal of library.signals) {
  const sourceAssets = join(repoRoot, signal.category, signal.name, "assets");
  const sourceSignalFolder = join(repoRoot, signal.category, signal.name);
  const targetAssets = join(publicRoot, "signals", signal.category, signal.name);

  mkdirSync(targetAssets, { recursive: true });

  for (const filename of ["plot.html", "report.html"]) {
    const source = join(sourceAssets, filename);
    if (existsSync(source)) {
      copyFileSync(source, join(targetAssets, filename));
    }
  }

  const readmePath = join(sourceSignalFolder, "README.md");
  if (existsSync(readmePath)) {
    copyFileSync(readmePath, join(targetAssets, "README.md"));
  }
}

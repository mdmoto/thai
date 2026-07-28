import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";

export function sites(projectId: string): Plugin {
  let root = process.cwd();

  return {
    name: "sites",
    apply: "build",
    configResolved(config) {
      root = config.root;
    },
    async closeBundle() {
      const outputDirectory = resolve(root, "dist", ".openai");
      const publicDirectory = resolve(root, "public");

      await rm(outputDirectory, { recursive: true, force: true });
      await mkdir(outputDirectory, { recursive: true });
      await writeFile(
        resolve(outputDirectory, "hosting.json"),
        `${JSON.stringify({ project_id: projectId }, null, 2)}\n`,
        "utf-8",
      );

      await cp(publicDirectory, resolve(root, "dist", "client"), {
        recursive: true,
        force: true,
      });
    },
  };
}

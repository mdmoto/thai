import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(webRoot, "../..");
const production = JSON.parse(
  readFileSync(resolve(webRoot, "deployment/production.json"), "utf8"),
);

const expectedApiOrigin =
  "https://market-twin-api-100282158973.asia-southeast1.run.app";
const retiredApiOrigin = [
  "https://",
  "ai",
  "-100282158973.asia-southeast1.run.app",
].join("");

function fail(message) {
  console.error(`Production configuration check failed: ${message}`);
  process.exitCode = 1;
}

if (production.apiOrigin !== expectedApiOrigin) {
  fail(`deployment/production.json must use ${expectedApiOrigin}`);
}

if (production.cloudRunService !== "market-twin-api") {
  fail("the only production Cloud Run service must be market-twin-api");
}

const configuredApiOrigin = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
if (
  configuredApiOrigin &&
  configuredApiOrigin !== expectedApiOrigin &&
  !/^http:\/\/(localhost|127\.0\.0\.1):8080$/.test(configuredApiOrigin)
) {
  fail(`NEXT_PUBLIC_API_URL points to an unapproved origin: ${configuredApiOrigin}`);
}

const headers = readFileSync(resolve(webRoot, "public/_headers"), "utf8");
if (!headers.includes(`connect-src 'self' ${expectedApiOrigin};`)) {
  fail("public/_headers does not allow the canonical production API");
}
if (headers.includes(["*", ".run.app"].join(""))) {
  fail("public/_headers must not allow wildcard Cloud Run origins");
}

const cloudBuild = readFileSync(resolve(repositoryRoot, "cloudbuild.yaml"), "utf8");
if (!cloudBuild.includes("\n      - market-twin-api\n")) {
  fail("cloudbuild.yaml does not deploy the canonical Cloud Run service");
}

const trackedFiles = execFileSync("git", ["ls-files", "-z"], {
  cwd: repositoryRoot,
  encoding: "utf8",
})
  .split("\0")
  .filter(Boolean);

for (const relativePath of trackedFiles) {
  const absolutePath = resolve(repositoryRoot, relativePath);
  if (!existsSync(absolutePath)) continue;
  const contents = readFileSync(absolutePath);
  if (contents.includes(Buffer.from(retiredApiOrigin))) {
    fail(`retired API origin found in ${relativePath}`);
  }
}

if (!process.exitCode) {
  console.log("Production endpoints are canonical and conflict-free.");
}

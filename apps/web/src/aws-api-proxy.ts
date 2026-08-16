/**
 * Cloudflare's HTTPS edge entry point for the private AWS origin.
 * Only /api/* is routed here; Pages continues to serve the public site.
 */
export default {
  async fetch(
    request: Request,
    env: { API_ORIGIN: string; ORIGIN_SHARED_SECRET: string },
  ): Promise<Response> {
    const incoming = new URL(request.url);
    const upstream = new URL(env.API_ORIGIN);
    const suffix = incoming.pathname.replace(/^\/api(?:\/|$)/, "/");
    upstream.pathname = suffix;
    upstream.search = incoming.search;
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.set("X-Origin-Verify", env.ORIGIN_SHARED_SECRET);
    return fetch(new Request(upstream, { method: request.method, headers, body: request.body }));
  },
};

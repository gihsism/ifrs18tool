/**
 * Reverse-proxy alenanikolskaia.com/IFRS18analysis/* -> Streamlit Cloud.
 *
 * The Streamlit app is configured with server.baseUrlPath = "IFRS18analysis",
 * so paths match 1:1 and we simply swap the hostname. WebSocket upgrades for
 * /IFRS18analysis/_stcore/stream are forwarded with the Upgrade header intact.
 *
 * Keeping everything on the same origin avoids Streamlit's cross-origin CSRF
 * block on file uploads, which was the reason the iframe embed failed.
 */

const UPSTREAM_HOST = "gihsism-ifrs18tool-app-lcitfr.streamlit.app";
const APP_PREFIX = "/IFRS18analysis";

export default {
  async fetch(request: Request, _env: unknown, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Only intercept the app's path prefix. Everything else (the rest of the
    // portfolio site) falls through to Vercel untouched.
    if (url.pathname !== APP_PREFIX && !url.pathname.startsWith(APP_PREFIX + "/")) {
      return fetch(request);
    }

    // Build the upstream URL. Path is left as-is because Streamlit is
    // configured to serve from /IFRS18analysis.
    const upstream = new URL(url.toString());
    upstream.hostname = UPSTREAM_HOST;
    upstream.protocol = "https:";
    upstream.port = "";

    // Preserve headers but rewrite Host so Streamlit/nginx routes correctly.
    const headers = new Headers(request.headers);
    headers.set("host", UPSTREAM_HOST);
    // Forward original client info, useful for Streamlit logs / rate limiting.
    const clientIp = request.headers.get("cf-connecting-ip");
    if (clientIp) headers.set("x-forwarded-for", clientIp);
    headers.set("x-forwarded-proto", "https");
    headers.set("x-forwarded-host", url.host);

    // Standard proxy fetch — Cloudflare passes WebSocket upgrades through
    // transparently as long as we forward the Upgrade/Connection headers,
    // which they already are in `request.headers`.
    const upstreamRequest = new Request(upstream.toString(), {
      method: request.method,
      headers,
      body: request.body,
      redirect: "manual",
    });

    const response = await fetch(upstreamRequest);

    // If upstream sent a redirect back to the streamlit.app hostname, rewrite
    // it so the browser stays on our domain.
    const location = response.headers.get("location");
    if (location) {
      try {
        const loc = new URL(location, `https://${UPSTREAM_HOST}`);
        if (loc.hostname === UPSTREAM_HOST) {
          loc.hostname = url.hostname;
          loc.protocol = url.protocol;
          loc.port = url.port;
          const rewritten = new Headers(response.headers);
          rewritten.set("location", loc.toString());
          return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: rewritten,
          });
        }
      } catch {
        /* location was relative or malformed — leave untouched */
      }
    }

    return response;
  },
};

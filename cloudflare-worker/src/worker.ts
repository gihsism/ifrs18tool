/**
 * Reverse-proxy alenanikolskaia.com/IFRS18analysis/* -> Streamlit Cloud.
 *
 * Streamlit serves at its root (no baseUrlPath). The Worker strips the
 * /IFRS18analysis prefix when forwarding. When Streamlit emits HTML or
 * redirects that reference its own absolute paths (e.g. /_stcore/stream),
 * we don't need to rewrite those — the next request from the browser to
 * alenanikolskaia.com/_stcore/stream won't match our route and will go to
 * Vercel, which 404s. To keep WebSocket + assets on the same origin, we
 * match more aggressively: any request with the referer starting with our
 * app URL also gets proxied.
 *
 * Keeping everything on the same origin avoids Streamlit's cross-origin
 * CSRF block on file uploads.
 */

const UPSTREAM_HOST = "gihsism-ifrs18tool-app-lcitfr.streamlit.app";
const APP_PREFIX = "/IFRS18analysis";

export default {
  async fetch(request: Request, _env: unknown, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Decide whether this request is for the IFRS 18 app. Two cases:
    //  1. The path itself is under /IFRS18analysis (page, callback, etc.)
    //  2. The path is a Streamlit internal (e.g. /_stcore/...) AND the
    //     request's Referer is our app page — means the app HTML made this
    //     call from the user's browser.
    const underPrefix =
      url.pathname === APP_PREFIX || url.pathname.startsWith(APP_PREFIX + "/");

    const referer = request.headers.get("referer") || "";
    const refererFromApp =
      referer.startsWith(`https://${url.host}${APP_PREFIX}`) ||
      referer.startsWith(`http://${url.host}${APP_PREFIX}`);

    const isStreamlitInternal =
      url.pathname.startsWith("/_stcore/") ||
      url.pathname.startsWith("/static/") ||
      url.pathname.startsWith("/component/") ||
      url.pathname.startsWith("/media/") ||
      url.pathname === "/oauth2callback" ||
      url.pathname.startsWith("/oauth2callback/");

    if (!underPrefix && !(isStreamlitInternal && refererFromApp)) {
      return fetch(request);
    }

    // Strip the /IFRS18analysis prefix from the upstream path. If the path
    // was Streamlit-internal (matched via referer), forward it as-is.
    const upstreamPath = underPrefix
      ? url.pathname.slice(APP_PREFIX.length) || "/"
      : url.pathname;

    const upstream = new URL(
      `https://${UPSTREAM_HOST}${upstreamPath}${url.search}`
    );

    const headers = new Headers(request.headers);
    headers.set("host", UPSTREAM_HOST);
    const clientIp = request.headers.get("cf-connecting-ip");
    if (clientIp) headers.set("x-forwarded-for", clientIp);
    headers.set("x-forwarded-proto", "https");
    headers.set("x-forwarded-host", url.host);

    const upstreamRequest = new Request(upstream.toString(), {
      method: request.method,
      headers,
      body: request.body,
      redirect: "manual",
    });

    const response = await fetch(upstreamRequest);

    // Rewrite Location headers that point back to streamlit.app so the
    // browser stays on alenanikolskaia.com.
    const location = response.headers.get("location");
    if (location) {
      try {
        const loc = new URL(location, `https://${UPSTREAM_HOST}`);
        if (loc.hostname === UPSTREAM_HOST) {
          loc.hostname = url.hostname;
          loc.protocol = url.protocol;
          loc.port = url.port;
          // Re-add the prefix if the upstream path is non-internal — so the
          // user ends up back at alenanikolskaia.com/IFRS18analysis/...
          if (
            !loc.pathname.startsWith("/_stcore/") &&
            !loc.pathname.startsWith("/static/") &&
            !loc.pathname.startsWith("/component/") &&
            !loc.pathname.startsWith("/media/") &&
            loc.pathname !== "/oauth2callback"
          ) {
            loc.pathname = APP_PREFIX + loc.pathname;
          }
          const rewritten = new Headers(response.headers);
          rewritten.set("location", loc.toString());
          return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: rewritten,
          });
        }
      } catch {
        /* leave relative / malformed locations untouched */
      }
    }

    return response;
  },
};

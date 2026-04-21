/**
 * Reverse-proxy alenanikolskaia.com/IFRS18analysis/* -> ifrs18tool.fly.dev.
 *
 * Streamlit runs with server.baseUrlPath = "IFRS18analysis" on Fly, so paths
 * match 1:1 — we just swap the hostname. All Streamlit-generated asset and
 * WebSocket URLs already include /IFRS18analysis, so the Worker's route
 * (alenanikolskaia.com/IFRS18analysis*) catches every request.
 *
 * Same origin from the browser's point of view, which avoids Streamlit's
 * cross-origin CSRF block on file uploads.
 */

const UPSTREAM_HOST = "ifrs18tool.fly.dev";

export default {
  async fetch(request: Request, _env: unknown, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Streamlit with baseUrlPath requires a trailing slash on the app root.
    // Redirect /IFRS18analysis to /IFRS18analysis/ so asset paths resolve.
    if (url.pathname === "/IFRS18analysis") {
      const withSlash = new URL(url.toString());
      withSlash.pathname = "/IFRS18analysis/";
      return Response.redirect(withSlash.toString(), 301);
    }

    // Everything under this Worker's route is app traffic — forward as-is.
    const upstream = new URL(url.toString());
    upstream.hostname = UPSTREAM_HOST;
    upstream.protocol = "https:";
    upstream.port = "";

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

    // Rewrite Location headers that point at the fly.dev host back to
    // alenanikolskaia.com so redirects stay on our domain.
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
        /* leave relative / malformed locations untouched */
      }
    }

    return response;
  },
};

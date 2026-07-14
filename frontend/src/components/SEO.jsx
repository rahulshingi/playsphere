import { useEffect } from "react";

/**
 * SEO — per-route <title>, meta description, canonical + OG tags.
 *
 * Lightweight hook-only component (no react-helmet dep). Updates document
 * head on mount and restores original values on unmount so back-nav returns
 * to the previous page's SEO cleanly.
 *
 * Usage:
 *   <SEO title="Book a venue — Kreeda Nation"
 *        description="Browse turfs, courts and coaches across India."
 *        canonical="/hire" />
 */
export default function SEO({ title, description, canonical, image, noindex = false }) {
  useEffect(() => {
    const original = {
      title: document.title,
      desc: getMeta("name", "description"),
      robots: getMeta("name", "robots"),
      canonical: getLinkHref("canonical"),
      ogTitle: getMeta("property", "og:title"),
      ogDesc: getMeta("property", "og:description"),
      ogUrl: getMeta("property", "og:url"),
      ogImage: getMeta("property", "og:image"),
      twTitle: getMeta("name", "twitter:title"),
      twDesc: getMeta("name", "twitter:description"),
      twImage: getMeta("name", "twitter:image"),
    };

    const origin = window.location.origin;
    const url = canonical ? `${origin}${canonical.startsWith("/") ? canonical : "/" + canonical}` : window.location.href;
    const img = image || `${origin}/kreeda-mark.png`;

    if (title) document.title = title;
    if (description) setMeta("name", "description", description);
    setMeta("name", "robots", noindex ? "noindex, nofollow" : "index, follow");
    setLink("canonical", url);
    if (title) setMeta("property", "og:title", title);
    if (description) setMeta("property", "og:description", description);
    setMeta("property", "og:url", url);
    setMeta("property", "og:image", img);
    if (title) setMeta("name", "twitter:title", title);
    if (description) setMeta("name", "twitter:description", description);
    setMeta("name", "twitter:image", img);

    return () => {
      document.title = original.title;
      if (original.desc !== null) setMeta("name", "description", original.desc);
      if (original.robots !== null) setMeta("name", "robots", original.robots);
      if (original.canonical) setLink("canonical", original.canonical);
      if (original.ogTitle !== null) setMeta("property", "og:title", original.ogTitle);
      if (original.ogDesc !== null) setMeta("property", "og:description", original.ogDesc);
      if (original.ogUrl !== null) setMeta("property", "og:url", original.ogUrl);
      if (original.ogImage !== null) setMeta("property", "og:image", original.ogImage);
      if (original.twTitle !== null) setMeta("name", "twitter:title", original.twTitle);
      if (original.twDesc !== null) setMeta("name", "twitter:description", original.twDesc);
      if (original.twImage !== null) setMeta("name", "twitter:image", original.twImage);
    };
  }, [title, description, canonical, image, noindex]);
  return null;
}

function getMeta(attr, name) {
  const el = document.querySelector(`meta[${attr}="${name}"]`);
  return el ? el.getAttribute("content") : null;
}
function setMeta(attr, name, content) {
  let el = document.querySelector(`meta[${attr}="${name}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, name);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}
function getLinkHref(rel) {
  const el = document.querySelector(`link[rel="${rel}"]`);
  return el ? el.getAttribute("href") : null;
}
function setLink(rel, href) {
  let el = document.querySelector(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", rel);
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

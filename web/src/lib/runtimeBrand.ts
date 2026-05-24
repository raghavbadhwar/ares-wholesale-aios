export type RuntimeBrand = {
  brand: string;
  brandShort: string;
  org: string;
};

declare global {
  interface Window {
    __ARES_DASHBOARD_BRAND__?: string;
    __ARES_DASHBOARD_BRAND_SHORT__?: string;
    __ARES_DASHBOARD_ORG__?: string;
  }
}

export function getRuntimeBrand(fallback: RuntimeBrand): RuntimeBrand {
  if (typeof window === "undefined") return fallback;

  return {
    brand: window.__ARES_DASHBOARD_BRAND__ || fallback.brand,
    brandShort: window.__ARES_DASHBOARD_BRAND_SHORT__ || fallback.brandShort,
    org: window.__ARES_DASHBOARD_ORG__ || fallback.org,
  };
}

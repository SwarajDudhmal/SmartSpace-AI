import '../../static/js/api.js';

declare global {
  interface Window {
    smartspaceFetch: (url: string, options?: RequestInit) => Promise<Response>;
  }
}

/** Share the job-aware request client with the vanilla Studio entry point. */
export const requestDesign = window.smartspaceFetch;

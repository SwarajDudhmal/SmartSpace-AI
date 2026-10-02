/* Shared by Vite components and the existing Studio scripts. */
(() => {
  if (window.smartspaceFetch) return;

  /** Return the final Response, polling HTTP 202 jobs with cancellation and timeout. */
  window.smartspaceFetch = async function smartspaceFetch(url, options = {}) {
    const controller = new AbortController();
    const externalSignal = options.signal;
    const abort = () => controller.abort(externalSignal?.reason);
    if (externalSignal?.aborted) abort();
    externalSignal?.addEventListener('abort', abort, { once: true });
    const timeout = setTimeout(() => controller.abort(new DOMException(
      'This design is taking too long. Please try again.', 'TimeoutError'
    )), 120000);

    try {
      let response = await fetch(url, { ...options, signal: controller.signal });
      let statusUrl;
      while (response.status === 202) {
        const job = await response.json();
        statusUrl = job.status_url || statusUrl;
        if (!statusUrl || !statusUrl.startsWith('/api/jobs/')) {
          throw new Error('The design service returned an invalid task response.');
        }
        // **Backpressure:** wait between polls; abort clears both timer and listener.
        await new Promise((resolve, reject) => {
          const onAbort = () => {
            clearTimeout(timer);
            reject(controller.signal.reason);
          };
          const timer = setTimeout(() => {
            controller.signal.removeEventListener('abort', onAbort);
            resolve();
          }, 750);
          if (controller.signal.aborted) onAbort();
          else controller.signal.addEventListener('abort', onAbort, { once: true });
        });
        response = await fetch(statusUrl, { signal: controller.signal, cache: 'no-store' });
      }
      return response;
    } finally {
      clearTimeout(timeout);
      externalSignal?.removeEventListener('abort', abort);
    }
  };
})();

import { motion, useReducedMotion } from 'framer-motion';

/** Display live progress without implying that a calculated percentage is known. */
export function DesignLoading({ message }: { message: string }) {
  const reduceMotion = useReducedMotion();
  return <motion.div className="ss-design-loading" role="status" aria-live="polite"
    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <motion.span className="ss-design-spinner" aria-hidden="true"
      animate={reduceMotion ? undefined : { rotate: 360 }}
      transition={{ repeat: Infinity, duration: 1, ease: 'linear' }} />
    <div><strong>{message}</strong><p>Please keep this page open while we prepare your room.</p></div>
  </motion.div>;
}

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';

type Option = { value: string; label: string; disabled?: boolean };
type Props = {
  id?: string;
  label: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  disabled?: boolean;
};

export function ResponsiveSelect({ id, label, value, options, onChange, disabled = false }: Props) {
  const generatedId = useId();
  const listId = `${id || generatedId}-options`;
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const typed = useRef({ text: '', time: 0 });
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [position, setPosition] = useState<{ left: number; top: number; width: number; maxHeight: number } | null>(null);
  const selected = options.find((option) => option.value === value);

  function show() {
    if (disabled) return;
    const index = options.findIndex((option) => option.value === value && !option.disabled);
    setActive(index >= 0 ? index : options.findIndex((option) => !option.disabled));
    setOpen(true);
  }

  function choose(index: number) {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    setOpen(false);
    trigger.current?.focus();
  }

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const bounds = trigger.current?.getBoundingClientRect();
      if (!bounds) return;
      const viewport = window.visualViewport;
      const leftEdge = (viewport?.offsetLeft || 0) + 8;
      const topEdge = (viewport?.offsetTop || 0) + 8;
      const rightEdge = leftEdge + (viewport?.width || window.innerWidth) - 16;
      const bottomEdge = topEdge + (viewport?.height || window.innerHeight) - 16;
      const below = Math.max(0, bottomEdge - bounds.bottom - 6);
      const above = Math.max(0, bounds.top - topEdge - 6);
      const desired = Math.min(320, options.length * 44 + 12);
      const useAbove = below < desired && above > below;
      const maxHeight = Math.min(desired, useAbove ? above : below);
      const width = Math.min(bounds.width, rightEdge - leftEdge);
      setPosition({
        left: Math.max(leftEdge, Math.min(bounds.left, rightEdge - width)),
        top: useAbove ? bounds.top - maxHeight - 6 : bounds.bottom + 6,
        width, maxHeight,
      });
    };
    const outside = (event: PointerEvent) => {
      if (!trigger.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) setOpen(false);
    };
    const onScroll = (event: Event) => {
      if (!menu.current?.contains(event.target as Node)) place();
    };
    place();
    document.addEventListener('pointerdown', outside);
    window.addEventListener('resize', place);
    window.addEventListener('scroll', onScroll, true);
    window.visualViewport?.addEventListener('resize', place);
    return () => {
      document.removeEventListener('pointerdown', outside);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', onScroll, true);
      window.visualViewport?.removeEventListener('resize', place);
    };
  }, [open, options.length]);

  useEffect(() => {
    if (open && position) menu.current?.querySelector<HTMLElement>(`[data-option-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active, open, Boolean(position)]);

  function keyboard(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape' || event.key === 'Tab') {
      if (open && event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); }
      setOpen(false);
      return;
    }
    if (['Enter', ' ', 'ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      if (!open) { show(); return; }
      if (event.key === 'Enter' || event.key === ' ') { choose(active); return; }
      const enabled = options.map((option, index) => option.disabled ? -1 : index).filter((index) => index >= 0);
      if (!enabled.length) return;
      const current = enabled.indexOf(active);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? enabled.length - 1
        : (current + (event.key === 'ArrowUp' ? -1 : 1) + enabled.length) % enabled.length;
      setActive(enabled[next]);
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      const now = Date.now();
      typed.current = { text: (now - typed.current.time > 700 ? '' : typed.current.text) + event.key.toLowerCase(), time: now };
      const index = options.findIndex((option) => !option.disabled && option.label.toLowerCase().startsWith(typed.current.text));
      if (!open) show();
      if (index >= 0) setActive(index);
    }
  }

  return <>
    <button ref={trigger} id={id} type="button" role="combobox" aria-label={label}
      aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? listId : undefined}
      aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
      disabled={disabled} className={`ss-select-trigger${open ? ' is-open' : ''}`}
      onClick={() => open ? setOpen(false) : show()} onKeyDown={keyboard}
      onBlur={(event) => { if (!menu.current?.contains(event.relatedTarget as Node)) setOpen(false); }}>
      <span className="ss-select-value">{selected?.label || '\u00a0'}</span>
      <svg className="ss-select-chevron" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="m5 7.5 5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </button>
    {open && position && createPortal(
      <div ref={menu} id={listId} role="listbox" aria-label={label} className="ss-select-menu" style={position}
        onPointerDown={(event) => { if (event.pointerType === 'mouse') event.preventDefault(); }}>
        {options.map((option, index) => <div key={option.value} id={`${listId}-${index}`} role="option"
          aria-selected={value === option.value} aria-disabled={option.disabled || undefined} data-option-index={index}
          className={`ss-select-option${active === index ? ' is-active' : ''}${value === option.value ? ' is-selected' : ''}`}
          onPointerMove={() => !option.disabled && setActive(index)}
          onClick={(event) => { event.preventDefault(); choose(index); }}>
          <span>{option.label}</span><span className="ss-select-check" aria-hidden="true">{value === option.value ? '✓' : ''}</span>
        </div>)}
      </div>, trigger.current?.closest('[role="dialog"]') || document.body,
    )}
  </>;
}

/** Keep existing vanilla form readers working while presenting the same React UI. */
export function NativeSelectAdapter({ select }: { select: HTMLSelectElement }) {
  const [value, setValue] = useState(select.value);
  const options = Array.from(select.options).filter((option) => option.value).map((option) => ({ value: option.value, label: option.text, disabled: option.disabled }));
  const label = select.getAttribute('aria-label') || select.labels?.[0]?.childNodes[0]?.textContent?.trim() || 'Choose an option';
  useEffect(() => {
    const sync = () => setValue(select.value);
    select.addEventListener('change', sync);
    return () => select.removeEventListener('change', sync);
  }, [select]);
  return <ResponsiveSelect id={`${select.id}-control`} label={label} value={value} options={options} disabled={select.disabled}
    onChange={(next) => { select.value = next; select.dispatchEvent(new Event('change', { bubbles: true })); }} />;
}

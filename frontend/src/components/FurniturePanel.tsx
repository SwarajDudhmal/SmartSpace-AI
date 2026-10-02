import { useEffect, useState } from 'react';
import type { FurnitureItem } from '../types';

type InventoryItem = FurnitureItem & { id: string; color?: string };
type InventorySnapshot = { items: InventoryItem[]; selectedId?: string; disabled?: boolean };
type FurnitureAction = 'select' | 'rotate' | 'swap' | 'delete';

declare global {
  interface Window {
    smartSpaceFurnitureInventory?: InventorySnapshot;
  }
}

const EMPTY_INVENTORY: InventorySnapshot = { items: [] };
const dimension = (value: number) => Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });

function dispatchAction(action: FurnitureAction, id: string) {
  window.dispatchEvent(new CustomEvent('smartspace:furniture-action', { detail: { action, id } }));
}

function FurnitureItemCard({ item, selected, disabled }: {
  item: InventoryItem; selected: boolean; disabled?: boolean;
}) {
  const name = item.label || item.type.toUpperCase();
  const actions = [
    { action: 'rotate', label: 'Rotate 90°', icon: '↻' },
    { action: 'swap', label: 'Swap furniture', icon: '⇄' },
    { action: 'delete', label: 'Delete furniture', icon: '×' },
  ] as const;

  return (
    <div className={`flex min-w-0 items-center justify-between gap-2 rounded-xl border p-3 transition-colors ${
      selected ? 'border-green-700 bg-green-50' : 'border-gray-200 bg-white hover:border-green-300'
    }`} data-furniture-id={item.id}>
      <button type="button" disabled={disabled} onClick={() => dispatchAction('select', item.id)}
        className="flex min-w-0 flex-1 items-center gap-2 rounded-md border-0 bg-transparent p-0 text-left focus-visible:outline-2 focus-visible:outline-green-700"
        aria-pressed={selected} aria-label={`Select ${name}`}>
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: item.color || '#347b58' }} aria-hidden="true" />
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium leading-tight text-gray-800" title={name}>{name}</span>
          <span className="mt-1 block text-xs leading-tight text-gray-500">
            {dimension(item.width)} × {dimension(item.depth)} m
          </span>
        </span>
      </button>
      <div className="flex shrink-0 items-center gap-1">
        {actions.map(({ action, label, icon }) => (
          <button key={action} type="button" disabled={disabled}
            onClick={() => dispatchAction(action, item.id)}
            title={label} aria-label={`${label}: ${name}`}
            className={`flex h-8 w-8 items-center justify-center rounded-md border-0 bg-transparent p-1.5 text-lg transition-colors hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-green-700 disabled:cursor-not-allowed disabled:opacity-40 ${
              action === 'delete' ? 'text-red-600 hover:bg-red-50' : 'text-gray-600'
            }`}>
            <span aria-hidden="true">{icon}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function FurniturePanel() {
  const [inventory, setInventory] = useState<InventorySnapshot>(() => window.smartSpaceFurnitureInventory || EMPTY_INVENTORY);

  useEffect(() => {
    const update = (event: Event) => setInventory((event as CustomEvent<InventorySnapshot>).detail);
    window.addEventListener('smartspace:furniture-updated', update);
    window.dispatchEvent(new CustomEvent('smartspace:request-furniture'));
    return () => window.removeEventListener('smartspace:furniture-updated', update);
  }, []);

  return (
    <div className="min-h-0 min-w-0 overflow-hidden">
      <div className="grid max-h-64 grid-cols-1 content-start gap-3 overflow-x-hidden overflow-y-auto overscroll-contain p-1 md:grid-cols-2 xl:grid-cols-3 [scrollbar-gutter:stable]"
        aria-label="Room furniture" data-furniture-grid>
        {inventory.items.length ? inventory.items.map((item) => (
          <FurnitureItemCard key={item.id} item={item} selected={inventory.selectedId === item.id} disabled={inventory.disabled} />
        )) : <p className="col-span-full m-0 py-4 text-center text-sm text-gray-500">Add furniture to start arranging your room.</p>}
      </div>
    </div>
  );
}

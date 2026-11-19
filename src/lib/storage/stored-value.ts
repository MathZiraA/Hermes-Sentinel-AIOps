import { useSyncExternalStore } from "react";

export interface StoredValue<T extends string> {
  /** Valor atual; no servidor e durante a hidratação é sempre o padrão (sem divergência de HTML). */
  use: () => T;
  get: () => T;
  set: (value: T) => void;
}

/**
 * Preferência salva no localStorage (tema, idioma…), lida com `useSyncExternalStore`.
 *
 * Só aceita valores da lista `allowed`; qualquer outra coisa salva vira o padrão. Se o armazenamento estiver
 * indisponível (modo privado, bloqueio), o valor vale só para esta página. Mudanças feitas em outra aba
 * chegam pelo evento `storage`.
 */
export function createStoredValue<T extends string>(
  key: string,
  fallback: T,
  allowed: readonly T[],
): StoredValue<T> {
  const listeners = new Set<() => void>();
  let memory: T | null = null;

  const isAllowed = (v: string | null): v is T =>
    v !== null && (allowed as readonly string[]).includes(v);

  const get = (): T => {
    try {
      const saved = localStorage.getItem(key);
      if (isAllowed(saved)) return saved;
    } catch {
      /* armazenamento indisponível */
    }
    return memory ?? fallback;
  };

  const set = (value: T) => {
    memory = value;
    try {
      localStorage.setItem(key, value);
    } catch {
      /* armazenamento indisponível: fica só em memória */
    }
    listeners.forEach((notify) => notify());
  };

  const subscribe = (notify: () => void) => {
    listeners.add(notify);
    const onStorage = (e: StorageEvent) => {
      if (e.key === key) notify();
    };
    window.addEventListener("storage", onStorage);
    return () => {
      listeners.delete(notify);
      window.removeEventListener("storage", onStorage);
    };
  };

  return {
    use: () => useSyncExternalStore(subscribe, get, () => fallback),
    get,
    set,
  };
}

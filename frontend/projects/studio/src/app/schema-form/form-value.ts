/**
 * Immutable path operations on a config document (9-3c).
 *
 * The schema form edits a *copy of the whole document*, not a value it built
 * from the schema: an area model pins only part of its tree (357 unpinned data
 * paths measured across the ALT config), and everything the form does not show
 * has to survive a save untouched. These helpers rebuild only the spine down
 * to the edited value, so untouched branches keep their identity — which is
 * both the preservation guarantee and what lets change detection stay cheap.
 */
export type ValuePath = readonly (string | number)[];

type Container = Record<string, unknown> | unknown[];

function isContainer(value: unknown): value is Container {
  return typeof value === 'object' && value !== null;
}

export function getAt(doc: unknown, path: ValuePath): unknown {
  let current: unknown = doc;
  for (const segment of path) {
    if (!isContainer(current)) return undefined;
    current = (current as Record<string | number, unknown>)[segment];
  }
  return current;
}

export function setAt<T>(doc: T, path: ValuePath, value: unknown): T {
  if (path.length === 0) return value as T;
  const [head, ...rest] = path;
  const container = shapeFor(doc, head);
  const child = rest.length === 0
    ? value
    : setAt((container as Record<string | number, unknown>)[head], rest, value);
  return writeInto(container, head, child) as T;
}

export function removeAt<T>(doc: T, path: ValuePath): T {
  if (path.length === 0 || !isContainer(doc)) return doc;
  const [head, ...rest] = path;
  const record = doc as Record<string | number, unknown>;
  if (rest.length > 0) {
    if (!isContainer(record[head])) return doc;
    const pruned = removeAt(record[head], rest);
    return (pruned === record[head] ? doc : writeInto(doc, head, pruned)) as T;
  }
  if (Array.isArray(doc)) {
    const index = Number(head);
    if (!Number.isInteger(index) || index < 0 || index >= doc.length) return doc;
    return [...doc.slice(0, index), ...doc.slice(index + 1)] as T;
  }
  if (!Object.hasOwn(record, head)) return doc;
  const { [head]: _dropped, ...remaining } = record;
  return remaining as T;
}

/**
 * Rename one key of the map at `path`, keeping its position — a map entry's
 * key is user data (RAG area names), so editing it must not make the row jump
 * to the bottom of the list mid-keystroke.
 */
export function renameKeyAt<T>(doc: T, path: ValuePath, from: string, to: string): T {
  if (from === to) return doc;
  const target = getAt(doc, path);
  if (!isContainer(target) || Array.isArray(target)) return doc;
  const record = target as Record<string, unknown>;
  if (!Object.hasOwn(record, from) || Object.hasOwn(record, to)) return doc;
  const renamed = Object.fromEntries(
    Object.entries(record).map(([key, value]) => [key === from ? to : key, value]),
  );
  return setAt(doc, path, renamed);
}

/**
 * The container to write `segment` into.
 *
 * A container that cannot hold the segment is REPLACED by one that can — an
 * array indexed by a name, or an object indexed by a number, is a shape
 * conflict between document and schema, and the alternative is worse: writing
 * `arr[Number('greeting')]` sets a property named `"NaN"` that `JSON.stringify`
 * drops, so the edit disappears without a trace and even the dirty check stays
 * false. The form never reaches this on purpose — `SchemaFieldComponent` shows
 * a conflicting value in the JSON editor instead of a group/list/map — so this
 * is the predictable floor, not the normal path.
 */
function shapeFor(doc: unknown, segment: string | number): Container {
  const wantsIndex = typeof segment === 'number';
  if (Array.isArray(doc)) return wantsIndex ? doc : {};
  if (isContainer(doc)) return wantsIndex ? [] : doc;
  return wantsIndex ? [] : {};
}

function writeInto(container: unknown, segment: string | number, value: unknown): Container {
  if (Array.isArray(container)) {
    const next = [...container];
    next[Number(segment)] = value;
    return next;
  }
  return { ...(container as Record<string, unknown>), [segment]: value };
}

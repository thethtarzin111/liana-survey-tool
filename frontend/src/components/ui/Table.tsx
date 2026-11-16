import type { ReactNode } from 'react';

export type Column<T> = {
  /** Unique key; also used as the default cell value (row[key]). */
  key: string;
  header: ReactNode;
  /** Label shown before the value when the table stacks on phones. Defaults to header text. */
  mobileLabel?: string;
  /** Custom cell content. */
  render?: (row: T) => ReactNode;
  /** Right-aligned tabular numbers. */
  numeric?: boolean;
  /** Header only for screen readers (e.g. an actions column). */
  hideHeader?: boolean;
};

type TableProps<T> = {
  /** Read by screen readers; say what the table lists. */
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** Shown in one cell when there are no rows. Use EmptyState around the table for the big version. */
  empty?: ReactNode;
};

/** Data table. On screens under 700 px each row turns into a labelled card, like the prototype. */
export function Table<T>({ caption, columns, rows, rowKey, empty = 'Nothing here yet.' }: TableProps<T>) {
  return (
    <div className="table-wrap">
      <table className="table table-stack">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? 'num' : undefined}>
                {c.hideHeader ? <span className="visually-hidden">{c.header}</span> : c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="table-empty" colSpan={columns.length} data-label="">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={c.numeric ? 'num' : undefined}
                    data-label={c.hideHeader ? '' : (c.mobileLabel ?? (typeof c.header === 'string' ? c.header : ''))}
                  >
                    {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

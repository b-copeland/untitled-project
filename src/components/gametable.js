import React, { useEffect, useState } from "react";
import Table from "react-bootstrap/Table";

// Phones are narrower than Bootstrap's `sm` breakpoint. Asked as "is it wide" so a screen that cannot answer counts as wide.
const WIDE_QUERY = "(min-width: 576px)";
const isWide = () => {
    try { return typeof window === "undefined" || !window.matchMedia || window.matchMedia(WIDE_QUERY).matches; } catch (e) { return true; }
};

/** Whether the screen is phone-sized, following it as it changes (a phone turned sideways). */
export function usePhone() {
    const [phone, setPhone] = useState(() => !isWide());
    useEffect(() => {
        if (typeof window === "undefined" || !window.matchMedia) return undefined;
        const query = window.matchMedia(WIDE_QUERY);
        const update = () => setPhone(!query.matches);
        update();
        if (query.addEventListener) { query.addEventListener("change", update); return () => query.removeEventListener("change", update); }
        query.addListener?.(update);
        return () => query.removeListener?.(update);
    }, []);
    return phone;
}

function cellsOf(columns, row, rowIndex) {
    const cells = [];
    for (let index = 0; index < columns.length; index++) {
        const column = columns[index];
        const span = Math.min(column.span ? column.span(row) : 1, columns.length - index);
        cells.push(
            <td key={index} colSpan={span > 1 ? span : undefined} className={column.className} style={{ textAlign: column.align || "right" }}>
                {column.cell(row, rowIndex)}
            </td>
        );
        index += span > 1 ? span - 1 : 0;
    }
    return cells;
}

/**
 * A table described by its columns instead of written out cell by cell.
 *
 *     <GameTable
 *       columns={[
 *         { header: "Structure", align: "left", cell: (row) => row.name },
 *         { header: "# Built", cell: (row) => row.built.toLocaleString() },
 *       ]}
 *       rows={rows}
 *     />
 *
 * Columns are right-aligned unless ``align`` says otherwise. ``rowKey`` picks a row's key (its ``key`` property by
 * default), ``rowClassName(row)`` adds a class to a row. A column may give ``span(row)``: a number of columns its cell
 * should cover for that row (the columns it covers are skipped), for a row that shows one message instead of its cells.
 *
 * A column with ``phoneRow: true`` (a slider) leaves the table's columns on a phone: its cell goes on a line of its own
 * under its row, across the whole width, so it is not squeezed into a narrow column. Its header is dropped there; the
 * control carries its own label.
 */
export function GameTable({ columns, rows, rowKey = (row) => row.key, rowClassName, className = "game-table", size = "sm", children }) {
    const phone = usePhone();
    const own = phone ? columns.filter((column) => column.phoneRow) : [];
    const inline = own.length ? columns.filter((column) => !column.phoneRow) : columns;
    const join = (...names) => names.filter(Boolean).join(" ") || undefined;
    return (
        <div className={join("table-scroll", own.length && "table-scroll-phone")}>
        <Table className={join(className, own.length && "game-table-phone")} hover size={size}>
            <thead>
                <tr>
                    {inline.map((column, index) => (
                        <th key={index} style={{ textAlign: column.align || "right" }}>{column.header}</th>
                    ))}
                </tr>
            </thead>
            <tbody>
                {rows.map((row, rowIndex) => {
                    const key = rowKey(row, rowIndex);
                    const rowClass = rowClassName ? rowClassName(row) : undefined;
                    if (!own.length) return <tr key={key} className={rowClass}>{cellsOf(inline, row, rowIndex)}</tr>;
                    return (
                        <React.Fragment key={key}>
                            <tr className={join(rowClass, "game-table-row-head")}>{cellsOf(inline, row, rowIndex)}</tr>
                            <tr className={join(rowClass, "game-table-row-own")}>
                                <td colSpan={inline.length} className="game-table-own-cell">
                                    {own.map((column, index) => <div key={index}>{column.cell(row, rowIndex)}</div>)}
                                </td>
                            </tr>
                        </React.Fragment>
                    );
                })}
                {children}
            </tbody>
        </Table>
        </div>
    );
}

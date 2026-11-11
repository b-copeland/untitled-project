import React from "react";
import Table from "react-bootstrap/Table";

function cellsOf(columns, row, rowIndex) {
    const cells = [];
    for (let index = 0; index < columns.length; index++) {
        const column = columns[index];
        const span = column.span ? column.span(row) : 1;
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
 */
export function GameTable({ columns, rows, rowKey = (row) => row.key, rowClassName, className = "game-table", size = "sm", children }) {
    return (
        <Table className={className} striped bordered hover size={size}>
            <thead>
                <tr>
                    {columns.map((column, index) => (
                        <th key={index} style={{ textAlign: column.align || "right" }}>{column.header}</th>
                    ))}
                </tr>
            </thead>
            <tbody>
                {rows.map((row, rowIndex) => (
                    <tr key={rowKey(row, rowIndex)} className={rowClassName ? rowClassName(row) : undefined}>
                        {cellsOf(columns, row, rowIndex)}
                    </tr>
                ))}
                {children}
            </tbody>
        </Table>
    );
}

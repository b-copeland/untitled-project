import React from "react";
import Table from "react-bootstrap/Table";

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
 * Text is left-aligned and numbers right-aligned by default (``align`` on a column overrides either). ``rowKey`` picks
 * a row's key (its ``key`` property by default).
 */
export function GameTable({ columns, rows, rowKey = (row) => row.key, className = "game-table", size = "sm", children }) {
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
                    <tr key={rowKey(row, rowIndex)}>
                        {columns.map((column, index) => (
                            <td key={index} className={column.className} style={{ textAlign: column.align || "right" }}>
                                {column.cell(row, rowIndex)}
                            </td>
                        ))}
                    </tr>
                ))}
                {children}
            </tbody>
        </Table>
    );
}

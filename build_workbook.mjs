import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

process.on("uncaughtException", error => {
  console.error("WORKBOOK_ERROR:", error?.message ?? String(error));
  process.exit(1);
});
process.on("unhandledRejection", error => {
  console.error("WORKBOOK_ERROR:", error?.message ?? String(error));
  process.exit(1);
});

const [payloadPath, outputPath, previewDir] = process.argv.slice(2);
if (!payloadPath || !outputPath || !previewDir) {
  throw new Error("usage: build_workbook.mjs payload.json output.xlsx preview_dir");
}
const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "User" });

const NAVY = "#17365D";
const BLUE = "#D9EAF7";
const BORDER = "#D5DBE3";
const GREEN = "#D9EAD3";
const RED = "#F4CCCC";

function columnName(index) {
  let n = index + 1, name = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function widthFor(header, rows, index) {
  let width = String(header).length + 2;
  for (const row of rows.slice(0, 200)) {
    const value = row[index];
    if (value !== null && value !== undefined) width = Math.max(width, String(value).length + 1);
  }
  if (/status/i.test(header)) return Math.min(Math.max(width, 24), 64);
  if (/^claim$/i.test(header)) return Math.min(Math.max(width, 24), 32);
  if (/label|interpret|criterion|role|full/i.test(header)) return Math.min(Math.max(width, 18), 46);
  if (/transformation|estimand|family|ablation|stage/i.test(header)) return Math.min(Math.max(width, 14), 30);
  return Math.min(Math.max(width, 11), 18);
}

const readme = workbook.worksheets.add("README");
readme.showGridLines = false;
readme.getRange("A1:F1").merge();
readme.getRange("A1").values = [[payload.title]];
readme.getRange("A1:F1").format = { fill: NAVY, font: { bold: true, color: "#FFFFFF", size: 16 }, rowHeight: 28, verticalAlignment: "center" };
readme.getRange("A3:B10").values = [
  ["Field", "Value"],
  ["Version", payload.version],
  ["Purpose", "Machine-readable source data for all integrated tables and figure panels"],
  ["Independent unit", "Clone; nested branches/repeats/draws are not treated as independent"],
  ["Stage 4 criteria passed", null],
  ["Stage 4 criteria total", null],
  ["Stage 5 strict loss families", "2 / 3 pass; channel projection strict ordering-drop test fails"],
  ["Stage 5 single-repeat scalar", "LCB 0.6942 < 0.72; exact frozen-repeat reproduction still passes"],
];
readme.getRange("A3:B3").format = { fill: BLUE, font: { bold: true, color: NAVY }, borders: { preset: "outside", style: "thin", color: BORDER } };
readme.getRange("A4:B10").format = { borders: { insideHorizontal: { style: "thin", color: BORDER } }, wrapText: true, verticalAlignment: "center" };
readme.getRange("A3:A10").format.font = { bold: true, color: NAVY };
readme.getRange("A:A").format.columnWidth = 27;
readme.getRange("B:B").format.columnWidth = 72;
readme.freezePanes.freezeRows(3);

for (const [sheetIndex, source] of payload.sheets.entries()) {
  const sheet = workbook.worksheets.add(source.name);
  sheet.showGridLines = false;
  const rows = [source.columns, ...source.rows];
  if (source.columns.length === 0) continue;
  const endCol = columnName(source.columns.length - 1);
  const endRow = rows.length;
  sheet.getRange(`A1:${endCol}${endRow}`).values = rows;
  sheet.getRange(`A1:${endCol}1`).format = {
    fill: NAVY,
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 30,
    borders: { bottom: { style: "medium", color: NAVY } },
  };
  if (endRow > 1) {
    sheet.getRange(`A2:${endCol}${endRow}`).format = {
      verticalAlignment: "center",
      borders: { insideHorizontal: { style: "thin", color: BORDER } },
    };
  }
  for (let col = 0; col < source.columns.length; col++) {
    const letter = columnName(col);
    const header = source.columns[col];
    sheet.getRange(`${letter}:${letter}`).format.columnWidth = widthFor(header, source.rows, col);
    const sample = source.rows.find(row => typeof row[col] === "number");
    if (sample) sheet.getRange(`${letter}2:${letter}${endRow}`).format.numberFormat = "0.0000";
    if (/pass|supported/i.test(header)) {
      const target = sheet.getRange(`${letter}2:${letter}${endRow}`);
      target.conditionalFormats.add("cellIs", { operator: "equal", formula: "TRUE", format: { fill: GREEN, font: { bold: true, color: "#274E13" } } });
      target.conditionalFormats.add("cellIs", { operator: "equal", formula: "FALSE", format: { fill: RED, font: { bold: true, color: "#990000" } } });
    }
  }
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add(`A1:${endCol}${endRow}`, true, `T${sheetIndex + 1}_${source.name.replace(/[^A-Za-z0-9]/g, "").slice(0, 18)}`);
}

// Assign cross-sheet formulas only after every target sheet exists.
readme.getRange("B7").formulas = [["=B8"]];
readme.getRange("B8").formulas = [["=COUNTA('Stage4_Validation'!F2:F7)"]];

const inspection = await workbook.inspect({ kind: "sheet,table", maxChars: 8000, tableMaxRows: 3, tableMaxCols: 5 });
console.log(inspection.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "formula error scan" });
console.log(errors.ndjson);

await fs.mkdir(previewDir, { recursive: true });
for (const sheetInfo of ["README", ...payload.sheets.map(s => s.name)]) {
  const blob = await workbook.render({ sheetName: sheetInfo, autoCrop: "all", scale: 1, format: "png" });
  const safe = sheetInfo.replace(/[^A-Za-z0-9_-]/g, "_");
  await fs.writeFile(path.join(previewDir, `${safe}.png`), new Uint8Array(await blob.arrayBuffer()));
}
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);

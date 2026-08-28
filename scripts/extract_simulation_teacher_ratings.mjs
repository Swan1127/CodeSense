import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [workbookPath, outputPath] = process.argv.slice(2);
if (!workbookPath || !outputPath) throw new Error("usage: extractor.mjs ratings.xlsx output.json");
const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const guide = workbook.worksheets.getItem("说明");
const ratings = workbook.worksheets.getItem("评分表");
const raterId = String(guide.getRange("B4").values[0][0] ?? "").trim();
const values = ratings.getRange("A1:O97").values;
const headers = values[0].map((value) => String(value ?? "").trim());
const rows = values.slice(1).map((source) => Object.fromEntries(headers.map((header, index) => [header, source[index] ?? ""])));
await fs.writeFile(outputPath, JSON.stringify({ rater_id: raterId, rows }, null, 2) + "\n", "utf8");

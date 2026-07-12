import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, "..");
const [inputPath, outputPath = path.join(projectRoot, "data", "history_import.json")] = process.argv.slice(2);

if (!inputPath) {
  throw new Error("Usage: node tools/extract_history.mjs <source-workbook.xlsx> [output-history.json]");
}

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const result = { source: inputPath, imported_at: new Date().toISOString(), sheets: {} };
for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  result.sheets[sheet.name] = used ? used.values : [];
}

await fs.writeFile(outputPath, JSON.stringify(result, null, 2), "utf8");
console.log(outputPath);

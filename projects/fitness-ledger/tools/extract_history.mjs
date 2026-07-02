import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = String.raw`C:\Users\26087\Desktop\fitness_tracker_clean_en.xlsx`;
const outputPath = String.raw`C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\fitness_tracker_app\data\history_import.json`;

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const result = { source: inputPath, imported_at: new Date().toISOString(), sheets: {} };
for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  result.sheets[sheet.name] = used ? used.values : [];
}

await fs.writeFile(outputPath, JSON.stringify(result, null, 2), "utf8");
console.log(outputPath);

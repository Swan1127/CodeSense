import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [sourcePath, outputPath] = process.argv.slice(2);
if (!sourcePath || !outputPath) throw new Error("usage: builder.mjs packet.json output.xlsx");
const packet = JSON.parse(await fs.readFile(sourcePath, "utf8"));
if (!Array.isArray(packet) || packet.length !== 96) throw new Error("teacher packet must contain exactly 96 rows, got " + packet.length);
for (const row of packet) {
  if ("condition" in row || "trajectory_id" in row) throw new Error("blinded packet source contains forbidden identifiers");
}

const workbook = Workbook.create();
const guide = workbook.worksheets.add("说明");
const ratings = workbook.worksheets.add("评分表");
guide.showGridLines = false;
ratings.showGridLines = false;
guide.getRange("A1:F1").merge();
guide.getRange("A1").values = [["三阶段引导式学习匿名对话评审"]];
guide.getRange("A1:F1").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF", size: 16 }, horizontalAlignment: "center", verticalAlignment: "center" };
guide.getRange("A1:F1").format.rowHeight = 30;
guide.getRange("A3").values = [["评审者编号"]];
guide.getRange("B3").values = [["请在下方填写，如 teacher_1"]];
guide.getRange("A4").values = [["rater_id"]];
guide.getRange("B4").values = [[""]];
guide.getRange("B4").format = { fill: "#FFF2CC", font: { bold: true, color: "#9C6500" } };
guide.getRange("A6:F6").merge();
guide.getRange("A6").values = [["评分说明"]];
guide.getRange("A6:F6").format = { fill: "#D9EAF7", font: { bold: true, color: "#17365D" } };
guide.getRange("A7:F14").values = [
  ["1—5分", "1=很差，2=较弱，3=基本合格，4=较好，5=很好", null, null, null, null],
  ["guidance_quality", "引导是否清楚、相关并能推动学生继续思考", null, null, null, null],
  ["cognitive_activation", "是否要求学生解释、推理或检查，而不是照抄答案", null, null, null, null],
  ["adaptivity", "是否根据学生当前暴露的问题调整后续引导", null, null, null, null],
  ["interaction_coherence", "对话是否连贯，后续回应是否承接前文", null, null, null, null],
  ["learner_agency", "学生是否仍承担主要分析和作答任务", null, null, null, null],
  ["answer_restraint", "是否避免过早给出完整算法、步骤或可提交代码", null, null, null, null],
  ["两个0/1字段", "0=不存在，1=存在完整代码或完整步骤过早泄漏", null, null, null, null]
];
guide.getRange("A16:F18").values = [
  ["操作要求", "两位教师各自使用独立副本，正式评分期间不要交换分数。", null, null, null, null],
  ["完整性", "96行均需完成六项评分和两个0/1判断；不确定时在comment中说明。", null, null, null, null],
  ["保密", "材料来自虚拟学生仿真，不包含真实学生信息；不得转发对话正文。", null, null, null, null]
];
guide.getRange("A3:A18").format.font = { bold: true, color: "#17365D" };
guide.getRange("A1:F18").format.wrapText = true;
guide.getRange("A:A").format.columnWidth = 24;
guide.getRange("B:F").format.columnWidth = 22;
guide.freezePanes.freezeRows(1);

const headers = ["review_id", "task_id", "difficulty", "persona_visible", "task_text", "transcript", "guidance_quality", "cognitive_activation", "adaptivity", "interaction_coherence", "learner_agency", "answer_restraint", "possible_complete_code_leakage", "possible_full_step_leakage", "comment"];
ratings.getRange("A1:O1").values = [headers];
ratings.getRange("A1:O1").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
const values = packet.map((row) => [row.review_id, row.task_id, row.difficulty, row.persona_visible, row.task_text, row.transcript, null, null, null, null, null, null, null, null, null]);
const lastRow = packet.length + 1;
ratings.getRange("A2:O" + lastRow).values = values;
ratings.getRange("G2:N" + lastRow).format.fill = "#FFFBE6";
ratings.getRange("G2:N" + lastRow).format.numberFormat = "0";
ratings.getRange("A1:O" + lastRow).format.wrapText = true;
ratings.getRange("A:A").format.columnWidth = 12;
ratings.getRange("B:C").format.columnWidth = 12;
ratings.getRange("D:E").format.columnWidth = 32;
ratings.getRange("F:F").format.columnWidth = 68;
ratings.getRange("G:N").format.columnWidth = 18;
ratings.getRange("O:O").format.columnWidth = 30;
ratings.getRange("A2:O" + lastRow).format.rowHeight = 72;
ratings.freezePanes.freezeRows(1);
ratings.freezePanes.freezeColumns(3);
ratings.dataValidations.add({ range: "G2:L" + lastRow, rule: { type: "whole", operator: "between", formula1: 1, formula2: 5 } });
ratings.dataValidations.add({ range: "M2:N" + lastRow, rule: { type: "list", values: [0, 1] } });
ratings.getRange("G2:L" + lastRow).conditionalFormats.add("colorScale", { colors: ["#F8696B", "#FFEB84", "#63BE7B"], thresholds: ["min", "50%", "max"] });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

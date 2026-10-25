// 开题答辩 PPT 构建脚本(pptxgenjs)
// 运行: NODE_PATH=$(npm root -g) node build-ppt.js
const pptxgen = require("pptxgenjs");

const W = 13.33, H = 7.5, M = 0.5;
// 调色板: 深墨蓝主导 + 琥珀强调(呼应功能图中"AI问答"核心模块色)
const NAVY = "1B3A6B";
const DARKBG = "0F2440";
const ACCENT = "D97706";
const TEXT = "1E293B";
const MUTED = "64748B";
const CARD = "F1F5F9";
const CARD2 = "FDF6EC";
const TINT = "EEF3FA";
const F = "Microsoft YaHei";

const shadow = () => ({ type: "outer", color: "94A3B8", blur: 8, offset: 2, angle: 45, opacity: 0.28 });
const bu = () => ({ code: "25B8", indent: 12 });

let p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "张一凡";
p.title = "企业内部文档智能检索系统 开题答辩";

function pageChrome(s, no, title, sub) {
  s.background = { color: "FFFFFF" };
  s.addText(title, { x: M, y: 0.32, w: W - 2 * M, h: 0.62, fontSize: 27, bold: true, color: NAVY, fontFace: F, margin: 0 });
  if (sub) s.addText(sub, { x: M, y: 0.94, w: W - 2 * M, h: 0.34, fontSize: 13, color: MUTED, fontFace: F, margin: 0 });
  s.addText(String(no).padStart(2, "0"), { x: W - 0.95, y: 0.34, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: "CBD5E1", fontFace: F, align: "right", margin: 0 });
}

function card(s, x, y, w, h, fill) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill || CARD }, rectRadius: 0.09, shadow: shadow(), line: { type: "none" } });
}

function arrowText(s, x, y, w, size) {
  s.addText("→", { x, y, w, h: 0.5, fontSize: size || 20, color: "94A3B8", bold: true, fontFace: F, align: "center", margin: 0 });
}

/* ── S1 封面 ── */
{
  const s = p.addSlide();
  s.background = { color: DARKBG };
  s.addText("毕业设计 · 开题答辩", { x: 0, y: 1.55, w: W, h: 0.4, fontSize: 16, color: ACCENT, fontFace: F, align: "center", charSpacing: 6, margin: 0 });
  s.addText("企业内部文档智能检索系统", { x: 0, y: 2.15, w: W, h: 0.95, fontSize: 44, bold: true, color: "FFFFFF", fontFace: F, align: "center", margin: 0 });
  s.addText("—— 基于 AI 问答知识库的设计与实现（SpringBoot + Vue）", { x: 0, y: 3.18, w: W, h: 0.5, fontSize: 17, color: "B6C2D9", fontFace: F, align: "center", margin: 0 });
  s.addText([
    { text: "汇报人：张一凡", options: { breakLine: true } },
    { text: "2026 年 11 月 7 日", options: {} }
  ], { x: 0, y: 5.55, w: W, h: 0.85, fontSize: 14, color: "8FA1BF", fontFace: F, align: "center", paraSpaceAfter: 6, margin: 0 });
  s.addNotes("开场:各位老师好,题目介绍。30秒内进入背景。");
}

/* ── S2 背景痛点 ── */
{
  const s = p.addSlide();
  pageChrome(s, 2, "企业文档的现实痛点", "为什么需要一个「智能检索与问答系统」");
  const items = [
    ["存放分散", "手册、报销、考勤、产品说明各处存放，想查一份制度不知道从哪份文件翻起"],
    ["查找低效", "关键词搜索只能命中「字面包含」的段落，换个说法就搜不到，新人上手成本高"],
    ["问答无依据", "直接问通用 AI，答案不知来自哪里，制度类问题不敢直接采用"]
  ];
  items.forEach((it, i) => {
    const x = M + i * 4.28;
    card(s, x, 1.55, 3.94, 3.1, "FFFFFF");
    s.addText(String(i + 1), { x: x + 0.3, y: 1.85, w: 0.9, h: 0.75, fontSize: 44, bold: true, color: ACCENT, fontFace: F, margin: 0 });
    s.addText(it[0], { x: x + 0.3, y: 2.7, w: 3.3, h: 0.45, fontSize: 19, bold: true, color: NAVY, fontFace: F, margin: 0 });
    s.addText(it[1], { x: x + 0.3, y: 3.2, w: 3.34, h: 1.3, fontSize: 13, color: TEXT, fontFace: F, lineSpacingMultiple: 1.25, margin: 0 });
  });
  card(s, M, 5.05, W - 2 * M, 1.15, TINT);
  s.addText([
    { text: "建设目标  ", options: { bold: true, color: NAVY } },
    { text: "让企业制度文档「存得进、查得快、问得准、答得有据」", options: { color: TEXT } }
  ], { x: M + 0.35, y: 5.05, w: W - 2 * M - 0.7, h: 1.15, fontSize: 17, fontFace: F, valign: "middle", margin: 0 });
  s.addNotes("三个痛点:分散/低效/无依据。落到目标一句话。约1.5分钟。");
}

/* ── S4 系统功能图 ── */
{
  const s = p.addSlide();
  pageChrome(s, 3, "系统功能图", "六大业务模块 · 35 项功能 · 一条业务主线贯穿");
  const iw = 11.9, ih = iw / (1600 / 826);
  s.addImage({ path: "assets/系统功能图.png", x: (W - iw) / 2, y: 1.28, w: iw, h: ih });
  s.addNotes("答辩主图:按模块从左到右讲全貌,先讲顶部业务主线,再逐模块点名功能,重点抛出问答是核心。约2分钟。");
}

/* ── S5 业务总链路 ── */
{
  const s = p.addSlide();
  pageChrome(s, 4, "业务总链路：五大业务环环相扣", "每个业务的产出，是下一个业务的原料");
  const steps = ["文档登记", "知识加工", "知识查找", "知识问答", "多轮会话"];
  const bw = 2.06, gap = 0.42;
  steps.forEach((t, i) => {
    const x = M + 0.1 + i * (bw + gap);
    card(s, x, 1.75, bw, 1.05, i === 3 ? NAVY : "FFFFFF");
    s.addText(t, { x, y: 1.75, w: bw, h: 1.05, fontSize: 17, bold: true, color: i === 3 ? "FFFFFF" : NAVY, fontFace: F, align: "center", valign: "middle", margin: 0 });
    if (i < steps.length - 1) arrowText(s, x + bw + 0.02, 2.02, gap - 0.04);
  });
  const rels = [
    ["文档登记 → 知识加工", "上传完成自动触发加工；加工结果回调更新文档状态"],
    ["知识加工 → 知识查找", "加工产出的知识库，是检索与问答共同的取材来源"],
    ["知识问答 → 知识查找", "问答业务内部调用检索取依据（系统内最关键的调用关系）"]
  ];
  rels.forEach((r, i) => {
    const y = 3.25 + i * 0.98;
    card(s, M, y, 8.0, 0.82, "FFFFFF");
    s.addText(r[0], { x: M + 0.3, y, w: 2.9, h: 0.82, fontSize: 13.5, bold: true, color: ACCENT, fontFace: F, valign: "middle", margin: 0 });
    s.addText(r[1], { x: M + 3.3, y, w: 4.5, h: 0.82, fontSize: 12.5, color: TEXT, fontFace: F, valign: "middle", lineSpacingMultiple: 1.15, margin: 0 });
  });
  card(s, 8.85, 3.25, 3.98, 2.78, TINT);
  s.addText("系统管理 · 贯穿全局", { x: 9.15, y: 3.5, w: 3.4, h: 0.45, fontSize: 15, bold: true, color: NAVY, fontFace: F, margin: 0 });
  s.addText([
    { text: "模型服务配置，免重启生效", options: { bullet: bu(), breakLine: true } },
    { text: "服务健康监测", options: { bullet: bu(), breakLine: true } },
    { text: "调用日志观测，问题可回查", options: { bullet: bu() } }
  ], { x: 9.15, y: 4.05, w: 3.45, h: 1.8, fontSize: 12.5, color: TEXT, fontFace: F, paraSpaceAfter: 8, margin: 0 });
  s.addNotes("链路+三条调用关系+系统管理贯穿。这是『业务之间关系与调用过程』要求的总览页。");
}

/* ── S6 模块① 文档管理 ── */
{
  const s = p.addSlide();
  pageChrome(s, 5, "模块① 文档管理 —— 业务链起点", "定义：企业文档进入系统的唯一入口与台账");
  card(s, M, 1.6, 5.4, 3.0, "FFFFFF");
  s.addText("五项功能", { x: M + 0.3, y: 1.82, w: 3.0, h: 0.4, fontSize: 15, bold: true, color: NAVY, fontFace: F, margin: 0 });
  s.addText([
    { text: "多格式上传：md / docx / pdf", options: { bullet: bu(), breakLine: true } },
    { text: "处理状态跟踪（见右图）", options: { bullet: bu(), breakLine: true } },
    { text: "文档下载", options: { bullet: bu(), breakLine: true } },
    { text: "文档删除：联动清理知识库", options: { bullet: bu(), breakLine: true } },
    { text: "知识块统计", options: { bullet: bu() } }
  ], { x: M + 0.3, y: 2.3, w: 4.8, h: 2.1, fontSize: 13.5, color: TEXT, fontFace: F, paraSpaceAfter: 9, margin: 0 });
  card(s, M, 4.85, 5.4, 1.35, CARD2);
  s.addText([
    { text: "联动删除规则  ", options: { bold: true, color: ACCENT } },
    { text: "删除文档时，其全部知识条目一并清理，保证台账与知识库永远一致", options: { color: TEXT } }
  ], { x: M + 0.3, y: 4.85, w: 4.8, h: 1.35, fontSize: 13, fontFace: F, valign: "middle", lineSpacingMultiple: 1.2, margin: 0 });

  card(s, 6.5, 1.6, 6.33, 4.6, "FFFFFF");
  s.addText("状态流转（业务衔接的可视化）", { x: 6.8, y: 1.85, w: 5.6, h: 0.4, fontSize: 15, bold: true, color: NAVY, fontFace: F, margin: 0 });
  const sts = [["待处理", "上传即建档，等待加工"], ["处理中", "知识库构建业务正在加工"], ["就绪", "可被检索与问答使用"]];
  sts.forEach((st, i) => {
    const y = 2.4 + i * 1.05;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 6.8, y, w: 1.7, h: 0.62, fill: { color: i === 2 ? NAVY : CARD }, rectRadius: 0.08, line: { type: "none" } });
    s.addText(st[0], { x: 6.8, y, w: 1.7, h: 0.62, fontSize: 14, bold: true, color: i === 2 ? "FFFFFF" : NAVY, fontFace: F, align: "center", valign: "middle", margin: 0 });
    s.addText(st[1], { x: 8.75, y, w: 3.9, h: 0.62, fontSize: 12.5, color: MUTED, fontFace: F, valign: "middle", margin: 0 });
    if (i < 2) s.addText("↓", { x: 7.45, y: y + 0.58, w: 0.4, h: 0.45, fontSize: 16, color: "94A3B8", bold: true, fontFace: F, align: "center", margin: 0 });
  });
  s.addText("加工失败 → 标记「失败」，支持重新处理（对账机制兜底）", { x: 6.8, y: 5.6, w: 5.7, h: 0.4, fontSize: 12, color: MUTED, fontFace: F, margin: 0 });
  s.addNotes("定义/功能/状态流转讲清与知识库的衔接:供给原料+回调状态。约1分钟。");
}

/* ── S7 模块② 知识库构建 ── */
{
  const s = p.addSlide();
  pageChrome(s, 6, "模块② 知识库构建 —— 自动加工厂", "定义：把「人读的文档」加工成「系统能用的知识」");
  const steps = [
    ["格式统一", "md/docx/pdf 统一为内部标准格式"],
    ["双层分块", "粗块留上下文，细块做精准匹配；查时细块定位、看粗块全文"],
    ["语义加工", "「报销流程」与「费用怎么报」可匹配同一内容"],
    ["入库索引", "建立可检索的知识库，状态回调「就绪」"]
  ];
  steps.forEach((st, i) => {
    const x = M + i * 3.15;
    card(s, x, 1.7, 2.85, 2.5, i === 1 ? TINT : "FFFFFF");
    s.addText(String(i + 1), { x: x + 0.25, y: 1.92, w: 0.6, h: 0.6, fontSize: 30, bold: true, color: ACCENT, fontFace: F, margin: 0 });
    s.addText(st[0], { x: x + 0.25, y: 2.55, w: 2.4, h: 0.4, fontSize: 16, bold: true, color: NAVY, fontFace: F, margin: 0 });
    s.addText(st[1], { x: x + 0.25, y: 2.98, w: 2.4, h: 1.1, fontSize: 12, color: TEXT, fontFace: F, lineSpacingMultiple: 1.2, margin: 0 });
    if (i < 3) arrowText(s, x + 2.85, 2.65, 0.3);
  });
  card(s, M, 4.7, W - 2 * M, 1.5, "FFFFFF");
  s.addText([
    { text: "对账兜底  ", options: { bold: true, color: ACCENT } },
    { text: "加工中途失败不丢文档：系统定期核对台账与知识库，失败文档自动标出、支持重新处理——保证上传的每一份文档都有着落", options: { color: TEXT } }
  ], { x: M + 0.35, y: 4.7, w: W - 2 * M - 0.7, h: 1.5, fontSize: 14.5, fontFace: F, valign: "middle", lineSpacingMultiple: 1.25, margin: 0 });
  s.addNotes("四步流水线+对账。双层分块是重点:细块定位粗块给全文。约1分钟。");
}

/* ── S8 模块③ 智能检索 ── */
{
  const s = p.addSlide();
  pageChrome(s, 7, "模块③ 智能检索 —— 快速通道", "定义：按查询意图，把最相关的知识段落排队找出");
  card(s, M, 1.7, 5.5, 1.05, "FFFFFF");
  s.addText("语义检索 · 理解意思", { x: M, y: 1.7, w: 5.5, h: 1.05, fontSize: 15, bold: true, color: NAVY, fontFace: F, align: "center", valign: "middle", margin: 0 });
  card(s, M, 3.0, 5.5, 1.05, "FFFFFF");
  s.addText("关键词检索 · 精确命中", { x: M, y: 3.0, w: 5.5, h: 1.05, fontSize: 15, bold: true, color: NAVY, fontFace: F, align: "center", valign: "middle", margin: 0 });
  s.addText("→", { x: 6.05, y: 2.62, w: 0.5, h: 0.5, fontSize: 22, color: "94A3B8", bold: true, fontFace: F, align: "center", margin: 0 });
  card(s, 6.6, 2.35, 2.6, 1.05, NAVY);
  s.addText("双路融合排序", { x: 6.6, y: 2.35, w: 2.6, h: 1.05, fontSize: 15, bold: true, color: "FFFFFF", fontFace: F, align: "center", valign: "middle", margin: 0 });
  arrowText(s, 9.25, 2.62, 0.4, 22);
  card(s, 9.7, 2.35, 3.1, 1.05, "FFFFFF");
  s.addText("精准重排", { x: 9.7, y: 2.35, w: 3.1, h: 1.05, fontSize: 15, bold: true, color: NAVY, fontFace: F, align: "center", valign: "middle", margin: 0 });
  card(s, M, 4.55, W - 2 * M, 0.95, "FFFFFF");
  s.addText([
    { text: "配套能力  ", options: { bold: true, color: NAVY } },
    { text: "按文档范围过滤（只在员工手册里查） · 命中段落原文高亮", options: { color: TEXT } }
  ], { x: M + 0.35, y: 4.55, w: W - 2 * M - 0.7, h: 0.95, fontSize: 14.5, fontFace: F, valign: "middle", margin: 0 });
  card(s, M, 5.75, W - 2 * M, 0.95, CARD2);
  s.addText([
    { text: "关键业务关系  ", options: { bold: true, color: ACCENT } },
    { text: "检索不只服务用户——AI 问答在内部调用它获取依据", options: { color: TEXT } }
  ], { x: M + 0.35, y: 5.75, w: W - 2 * M - 0.7, h: 0.95, fontSize: 14.5, fontFace: F, valign: "middle", margin: 0 });
  s.addNotes("双路并行→融合→重排图示+过滤/高亮+被问答调用。约1分钟。");
}

/* ── S9 模块④ AI问答·七步流程 ── */
{
  const s = p.addSlide();
  pageChrome(s, 8, "模块④ AI 知识问答（核心）—— 七步流程", "定义：像懂制度的同事一样作答，每句话都有出处");
  const steps = [
    ["理解", "口语问题整理为清晰表达"],
    ["分流", "判断简单 / 复杂问题"],
    ["分解", "复杂问题拆为子问题"],
    ["取据", "调用智能检索取回依据"],
    ["评估", "依据不足自动补充检索"],
    ["生成", "只依据查到的内容作答并标注引用"],
    ["校验", "核对答案有据可依，不通过则重答"]
  ];
  const bw = 1.62, gap2 = 0.13;
  steps.forEach((st, i) => {
    const x = M + i * (bw + gap2);
    card(s, x, 1.75, bw, 2.15, i >= 3 && i <= 5 ? TINT : "FFFFFF");
    s.addText(String(i + 1), { x: x + 0.16, y: 1.92, w: 0.5, h: 0.5, fontSize: 24, bold: true, color: ACCENT, fontFace: F, margin: 0 });
    s.addText(st[0], { x: x + 0.16, y: 2.44, w: bw - 0.3, h: 0.38, fontSize: 15.5, bold: true, color: NAVY, fontFace: F, margin: 0 });
    s.addText(st[1], { x: x + 0.16, y: 2.84, w: bw - 0.28, h: 0.95, fontSize: 10.5, color: MUTED, fontFace: F, lineSpacingMultiple: 1.12, margin: 0 });
  });
  card(s, M, 4.35, 7.9, 1.9, CARD2);
  s.addText("底线规则：无依据拒答", { x: M + 0.35, y: 4.6, w: 7.2, h: 0.45, fontSize: 16, bold: true, color: ACCENT, fontFace: F, margin: 0 });
  s.addText("知识库中没有相关制度时，系统如实回答「现有资料无法回答」，并建议换问法或补充文档——宁可说不知道，绝不编造。这是制度类问答的底线。",
    { x: M + 0.35, y: 5.1, w: 7.2, h: 1.0, fontSize: 13.5, color: TEXT, fontFace: F, lineSpacingMultiple: 1.3, margin: 0 });
  card(s, 8.85, 4.35, 3.98, 1.9, "FFFFFF");
  s.addText("举例（复杂问题）", { x: 9.15, y: 4.6, w: 3.4, h: 0.4, fontSize: 14, bold: true, color: NAVY, fontFace: F, margin: 0 });
  s.addText("「经理去其他城市出差，住宿补贴比一线员工多多少？」→ 分解为两个子问题分别查证 → 汇总对比结论",
    { x: 9.15, y: 5.05, w: 3.45, h: 1.1, fontSize: 12, color: TEXT, fontFace: F, lineSpacingMultiple: 1.25, margin: 0 });
  s.addNotes("核心页,放慢:七步流程+拒答底线+经理补贴例子。约2.5分钟。");
}

/* ── S11 系统演示 ── */
{
  const s = p.addSlide();
  pageChrome(s, 9, "系统演示（已全部实现并联调通过）", "演示路径：上传 → 状态就绪 → 问答 → 引用溯源 → 检索");
  const iw = 8.35, ih = iw / (1600 / 900);
  s.addImage({ path: "assets/演示-问答页.png", x: M, y: 1.5, w: iw, h: ih });
  card(s, 9.15, 1.5, 3.68, 4.7, "FFFFFF");
  s.addText("演示动作清单", { x: 9.45, y: 1.75, w: 3.1, h: 0.4, fontSize: 15, bold: true, color: NAVY, fontFace: F, margin: 0 });
  s.addText([
    { text: "上传新文档，状态自动流转为「就绪」并统计知识块", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "新建会话提问「年假有几天」，回答流式输出并带引用", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "点击引用编号，打开原文段落核对", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "复杂问题自动分解查证，思考过程可展开", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "检索页双路排序 + 原文高亮", options: { bullet: { type: "number" } } }
  ], { x: 9.45, y: 2.25, w: 3.15, h: 3.7, fontSize: 12, color: TEXT, fontFace: F, paraSpaceAfter: 10, lineSpacingMultiple: 1.15, margin: 0 });
  s.addNotes("左图即真实系统截图。演示1.5分钟,按清单走。");
}

/* ── S12 后续规划 ── */
{
  const s = p.addSlide();
  pageChrome(s, 10, "后续规划", "开题之后，系统继续完善的方向");
  const plans = [
    ["权限细化", "按部门隔离文档与知识范围"],
    ["文档版本管理", "制度更新后新旧版本可追溯"],
    ["知识库运营统计", "高频问题、未答问题分析，反哺文档建设"],
    ["检索质量评测", "固定题库量化评估回答质量，支撑论文实验章节"]
  ];
  plans.forEach((it, i) => {
    const x = M + (i % 2) * 6.35, y = 1.7 + Math.floor(i / 2) * 1.85;
    card(s, x, y, 5.95, 1.55, "FFFFFF");
    s.addText(String(i + 1), { x: x + 0.3, y: y + 0.36, w: 0.75, h: 0.8, fontSize: 40, bold: true, color: ACCENT, fontFace: F, margin: 0 });
    s.addText(it[0], { x: x + 1.15, y: y + 0.25, w: 4.5, h: 0.45, fontSize: 16.5, bold: true, color: NAVY, fontFace: F, margin: 0 });
    s.addText(it[1], { x: x + 1.15, y: y + 0.75, w: 4.6, h: 0.6, fontSize: 12.5, color: MUTED, fontFace: F, margin: 0 });
  });
  card(s, M, 5.6, W - 2 * M, 0.95, TINT);
  s.addText([
    { text: "当前进度  ", options: { bold: true, color: NAVY } },
    { text: "六大模块 · 35 项功能已全部实现并联调通过，可现场演示", options: { color: TEXT } }
  ], { x: M + 0.35, y: 5.6, w: W - 2 * M - 0.7, h: 0.95, fontSize: 15, fontFace: F, valign: "middle", margin: 0 });
  s.addNotes("四项规划+当前进度声明。约1分钟。");
}

/* ── S13 结尾 ── */
{
  const s = p.addSlide();
  s.background = { color: DARKBG };
  s.addText("恳请各位老师批评指正", { x: 0, y: 2.9, w: W, h: 0.9, fontSize: 38, bold: true, color: "FFFFFF", fontFace: F, align: "center", margin: 0 });
  s.addText("企业内部文档智能检索系统 · 开题答辩", { x: 0, y: 4.0, w: W, h: 0.5, fontSize: 15, color: "8FA1BF", fontFace: F, align: "center", margin: 0 });
  s.addNotes("结尾致谢,进入问答。备:与通用AI区别/复杂问题判断/为何不能立即可用/工作量主体。");
}

p.writeFile({ fileName: "开题答辩.pptx" }).then(() => console.log("PPT written"));

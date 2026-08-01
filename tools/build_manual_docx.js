/**
 * Build the user manual as a Word document.
 *
 * Consumes the block structure emitted by tools/manual_parse.py, so
 * docs/USER_MANUAL.md remains the single source of truth for the in-app page, the
 * PDF, and this.
 *
 * Usage:  node tools/build_manual_docx.js <blocks.json> <out.docx> <version>
 */

const fs = require("fs");
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, LevelFormat,
  PageBreak, PageNumber, PageOrientation, Packer, Paragraph, ShadingType, Table,
  TableCell, TableRow, TableOfContents, TextRun, VerticalAlign, WidthType,
} = require("docx");

const [, , BLOCKS_PATH, OUT_PATH, VERSION] = process.argv;

// US Letter in DXA (1440 per inch); 1" margins leave 9360 for content.
const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1440;
const CONTENT_W = PAGE_W - MARGIN * 2;

const NAVY = "1F3A5F";
const CALLOUT_BG = "F4F6F8";
const RULE = "C9D2DB";

const blocks = JSON.parse(fs.readFileSync(BLOCKS_PATH, "utf8"));

// -- inline runs ---------------------------------------------------------------

function toRuns(runs, opts = {}) {
  const size = opts.size || 22;
  return runs.map((r) =>
    new TextRun({
      text: r.text,
      bold: r.bold || opts.bold || false,
      italics: r.italic || opts.italics || false,
      font: r.code ? "Consolas" : undefined,
      size: r.code ? size - 2 : size,
      color: opts.color,
    })
  );
}

function plain(runs) {
  return runs.map((r) => r.text).join("");
}

// -- tables -------------------------------------------------------------------

function buildTable(block) {
  const weights = block.weights;
  const n = weights.length;
  // Column widths must sum exactly to the table width, and every cell needs its
  // own matching width or Google Docs collapses the layout.
  let widths = weights.map((w) => Math.floor((w / n) * CONTENT_W));
  const drift = CONTENT_W - widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += drift;

  const size = n >= 5 ? 16 : 18;

  const cell = (runs, { bold = false, header = false, index }) =>
    new TableCell({
      width: { size: widths[index], type: WidthType.DXA },
      verticalAlign: VerticalAlign.TOP,
      shading: header
        ? { type: ShadingType.CLEAR, fill: "EEF2F6", color: "auto" }
        : undefined,
      margins: { top: 80, bottom: 80, left: 110, right: 110 },
      children: [
        new Paragraph({
          spacing: { before: 0, after: 0 },
          children: toRuns(runs, { size, bold }),
        }),
      ],
    });

  const rows = [
    new TableRow({
      tableHeader: true,
      children: block.header.map((h, i) =>
        cell(h, { bold: true, header: true, index: i })
      ),
    }),
    ...block.rows.map(
      (r) =>
        new TableRow({
          children: r.map((c, i) => cell(c, { index: i })),
        })
    ),
  ];

  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 8, color: NAVY },
      bottom: { style: BorderStyle.SINGLE, size: 8, color: NAVY },
      left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
    },
    rows,
  });
}

// -- body ---------------------------------------------------------------------

const HEADINGS = {
  2: HeadingLevel.HEADING_1,
  3: HeadingLevel.HEADING_2,
  4: HeadingLevel.HEADING_3,
};

function buildBody() {
  const out = [];
  let seenTitle = false;
  let i = 0;

  while (i < blocks.length) {
    const b = blocks[i];

    if (b.type === "heading") {
      if (b.level === 1 && !seenTitle) {
        seenTitle = true; // the title page carries it
        i += 1;
        continue;
      }
      // Replace the markdown Contents list with a real Word field-based TOC.
      if (b.text.toLowerCase() === "contents") {
        i += 1;
        while (i < blocks.length && ["list", "rule"].includes(blocks[i].type)) i += 1;
        continue;
      }
      out.push(
        new Paragraph({
          heading: HEADINGS[b.level] || HeadingLevel.HEADING_4,
          spacing: { before: b.level === 2 ? 360 : 260, after: 120 },
          keepNext: true,
          children: toRuns(b.runs, {
            size: b.level === 2 ? 30 : b.level === 3 ? 26 : 23,
            bold: true,
            color: NAVY,
          }),
        })
      );
      i += 1;
      continue;
    }

    if (b.type === "paragraph") {
      out.push(
        new Paragraph({
          spacing: { after: 140, line: 276 },
          children: toRuns(b.runs),
        })
      );
      i += 1;
      continue;
    }

    if (b.type === "list") {
      b.items.forEach((item) => {
        out.push(
          new Paragraph({
            spacing: { after: 60, line: 276 },
            ...(b.ordered
              ? { numbering: { reference: "manual-numbers", level: 0 } }
              : { numbering: { reference: "manual-bullets", level: 0 } }),
            children: toRuns(item),
          })
        );
      });
      i += 1;
      continue;
    }

    if (b.type === "callout") {
      b.paragraphs.forEach((p, idx) => {
        out.push(
          new Paragraph({
            spacing: {
              before: idx === 0 ? 160 : 60,
              after: idx === b.paragraphs.length - 1 ? 160 : 60,
              line: 276,
            },
            indent: { left: 260, right: 200 },
            shading: { type: ShadingType.CLEAR, fill: CALLOUT_BG, color: "auto" },
            border: {
              left: { style: BorderStyle.SINGLE, size: 18, color: NAVY, space: 12 },
            },
            children: toRuns(p),
          })
        );
      });
      i += 1;
      continue;
    }

    if (b.type === "table") {
      out.push(buildTable(b));
      out.push(new Paragraph({ spacing: { after: 180 }, children: [] }));
      i += 1;
      continue;
    }

    // Horizontal rules: headings already provide the visual breaks.
    i += 1;
  }
  return out;
}

// -- title page ---------------------------------------------------------------

function rule(color, size) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    border: { bottom: { style: BorderStyle.SINGLE, size, color } },
    children: [],
  });
}

function titlePage() {
  const centered = (children, spacing = {}) =>
    new Paragraph({ alignment: AlignmentType.CENTER, spacing, children });

  return [
    new Paragraph({ spacing: { before: 2400 }, children: [] }),
    rule(NAVY, 18),
    centered(
      [new TextRun({ text: "Public Assistance Workbench", bold: true, size: 56, color: NAVY })],
      { before: 200, after: 100 }
    ),
    centered([new TextRun({ text: "User Manual", size: 34, color: NAVY })], { after: 140 }),
    rule(NAVY, 18),
    centered(
      [
        new TextRun({
          text: "A FEMA Public Assistance reimbursement workbench and training simulator",
          size: 24,
        }),
      ],
      { before: 420, after: 520 }
    ),
    centered(
      [
        new TextRun({
          text:
            "Built against the FEMA Public Assistance Program and Policy Guide, Version 5 " +
            "Amended (January 2025); FEMA Policy FP-104-23-001, Public Assistance " +
            "Simplified Procedures (January 2023); 44 CFR Part 206; 2 CFR Part 200; and " +
            "the Disaster Recovery Reform Act of 2018.",
          size: 19,
        }),
      ],
      { after: 400 }
    ),
    centered(
      [
        new TextRun({
          text:
            "Not affiliated with FEMA. This is a planning and training aid. Dollar " +
            "thresholds are indexed annually and cost shares are set by each " +
            "declaration. Verify every figure against the current PAPPG and your own " +
            "award before relying on it.",
          size: 19,
          italics: true,
        }),
      ],
      { after: 900 }
    ),
    centered([new TextRun({ text: `Application version ${VERSION}`, size: 19 })], {
      after: 60,
    }),
    centered([
      new TextRun({
        text: new Date().toLocaleDateString("en-US", {
          year: "numeric",
          month: "long",
          day: "numeric",
        }),
        size: 19,
      }),
    ]),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

function tocSection() {
  return [
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { after: 200 },
      children: [new TextRun({ text: "Contents", bold: true, size: 30, color: NAVY })],
    }),
    new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

// -- document -----------------------------------------------------------------

const doc = new Document({
  creator: "Public Assistance Workbench",
  title: "Public Assistance Workbench — User Manual",
  description: "User manual for the FEMA Public Assistance reimbursement workbench",
  // Without this the table of contents field is present but empty until the reader
  // right-clicks and updates it, which nobody does. This makes Word populate it on
  // open instead.
  features: { updateFields: true },
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 22 }, paragraph: { spacing: { line: 276 } } },
    },
  },
  numbering: {
    config: [
      {
        reference: "manual-bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 260 } } },
          },
        ],
      },
      {
        reference: "manual-numbers",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 260 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.PORTRAIT },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
        titlePage: true,
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              tabStops: [{ type: "right", position: CONTENT_W }],
              border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE } },
              children: [
                new TextRun({ text: "Public Assistance Workbench", size: 18, color: NAVY }),
                new TextRun({ text: "\tUser Manual", size: 18, color: NAVY }),
              ],
            }),
          ],
        }),
        first: new Header({ children: [] }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new TextRun({ children: [PageNumber.CURRENT], size: 18 })],
            }),
          ],
        }),
        first: new Footer({ children: [] }),
      },
      children: [...titlePage(), ...tocSection(), ...buildBody()],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT_PATH, buf);
  console.log(`Wrote ${OUT_PATH} (${(buf.length / 1024).toFixed(0)} KB)`);
});

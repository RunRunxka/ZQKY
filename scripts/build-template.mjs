import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import PizZip from 'pizzip';
import { JSDOM } from 'jsdom';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'assets/templates/source/teacher-standard.docx');
const bytes = fs.readFileSync(source),
  zip = new PizZip(bytes);
const dom = new JSDOM(zip.file('word/document.xml').asText(), { contentType: 'text/xml' });
const doc = dom.window.document,
  W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const children = (el, name) => Array.from(el.children).filter((e) => e.localName === name);
const tables = Array.from(doc.getElementsByTagNameNS(W, 'tbl'));
if (tables.length !== 2) throw Error('模板结构已变化：预期2张表');
const schema = {
  version: 1,
  sourceSha256: crypto.createHash('sha256').update(bytes).digest('hex'),
  page: {
    widthTwips: 11900,
    heightTwips: 17160,
    topTwips: 840,
    bottomTwips: 840,
    leftTwips: 940,
    rightTwips: 940,
  },
  tables: tables.map((t) => ({
    grid: Array.from(t.getElementsByTagNameNS(W, 'gridCol')).map((c) => +c.getAttributeNS(W, 'w')),
    rows: children(t, 'tr').map((r) => ({
      minHeightTwips: +(r.getElementsByTagNameNS(W, 'trHeight')[0]?.getAttributeNS(W, 'val') ?? 0),
      cells: children(r, 'tc').map((c) => ({
        label: Array.from(c.getElementsByTagNameNS(W, 't'))
          .map((t) => t.textContent)
          .join(''),
        colSpan: +(c.getElementsByTagNameNS(W, 'gridSpan')[0]?.getAttributeNS(W, 'val') ?? 1),
        vMerge: c.getElementsByTagNameNS(W, 'vMerge')[0]?.getAttributeNS(W, 'val') ?? null,
      })),
    })),
  })),
};
const cell = (ti, ri, ci) => children(children(tables[ti], 'tr')[ri], 'tc')[ci];
function setCell(ti, ri, ci, text) {
  const c = cell(ti, ri, ci),
    p = children(c, 'p')[0].cloneNode(true);
  const pPr = children(p, 'pPr')[0]?.cloneNode(true),
    rPr = p.getElementsByTagNameNS(W, 'rPr')[0]?.cloneNode(true);
  p.replaceChildren();
  if (pPr) p.append(pPr);
  const r = doc.createElementNS(W, 'w:r');
  if (rPr) r.append(rPr);
  const t = doc.createElementNS(W, 'w:t');
  t.textContent = text;
  r.append(t);
  p.append(r);
  children(c, 'p').forEach((e) => e.remove());
  c.append(p);
}
setCell(0, 0, 1, '{title}');
setCell(0, 0, 3, '{totalLessons}');
setCell(0, 0, 5, '第{currentLessonNo}课时');
setCell(0, 1, 1, '{lessonTypesText}');
setCell(0, 2, 1, '{coreCompetencies}');
setCell(0, 3, 1, '{keyPoints}');
setCell(0, 4, 1, '{teachingDesign}');
setCell(0, 6, 1, '{firstDesign}');
setCell(0, 6, 2, '{firstSecondary}');
setCell(1, 1, 1, '{restDesign}');
setCell(1, 1, 2, '{restSecondary}');
setCell(1, 2, 1, '{exercises}');
setCell(1, 3, 1, '{reflection}');
zip.file('word/document.xml', new dom.window.XMLSerializer().serializeToString(doc));
fs.mkdirSync(path.join(root, 'apps/web/public/templates'), { recursive: true });
fs.mkdirSync(path.join(root, 'apps/web/src/features/lesson-plan/services/schema'), {
  recursive: true,
});
fs.writeFileSync(
  path.join(root, 'apps/web/public/templates/lesson-plan-template.docx'),
  zip.generate({ type: 'nodebuffer' }),
);
fs.writeFileSync(
  path.join(root, 'apps/web/src/features/lesson-plan/services/schema/lesson-plan.schema.json'),
  JSON.stringify(schema, null, 2),
);
console.log(
  JSON.stringify(
    {
      tables: schema.tables.map((t) => ({ grid: t.grid, rows: t.rows.length })),
      sourceSha256: schema.sourceSha256,
    },
    null,
    2,
  ),
);

import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import PizZip from 'pizzip';
import { JSDOM } from 'jsdom';
const root = fileURLToPath(new URL('../', import.meta.url));
const ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const hash = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex');
const xml = (bytes) =>
  new JSDOM(new PizZip(bytes).file('word/document.xml').asText(), { contentType: 'text/xml' })
    .window.document;
const normalize = (e) => ({
  name: e.localName,
  ns: e.namespaceURI,
  attributes: Array.from(e.attributes)
    .filter((a) => !a.name.startsWith('xmlns'))
    .map((a) => [a.namespaceURI, a.localName, a.value])
    .sort(),
  children: Array.from(e.children).map(normalize),
  text: e.children.length ? '' : e.textContent.trim(),
});
export function verifyDocx(output) {
  const source = xml(
      fs.readFileSync(path.join(root, 'assets/templates/source/teacher-standard.docx')),
    ),
    doc = xml(output);
  const results = {};
  for (const name of ['tblPr', 'tblGrid', 'tcPr', 'trHeight', 'sectPr']) {
    const value = (d) =>
      JSON.stringify(Array.from(d.getElementsByTagNameNS(ns, name)).map(normalize));
    results[name] = value(source) === value(doc);
  }
  const text = Array.from(doc.getElementsByTagNameNS(ns, 't'))
    .map((t) => t.textContent)
    .join('');
  results.noUnfilledTags = !/\{(?:title|firstDesign|restDesign|reflection)\}/.test(text);
  return results;
}
export function verifySource() {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(root, 'assets/templates/source/manifest.json'), 'utf8'),
  );
  return {
    original: hash(fs.readFileSync(path.join(root, manifest.original))) === manifest.sha256,
    source:
      hash(fs.readFileSync(path.join(root, 'assets/templates/source', manifest.file))) ===
      manifest.sha256,
  };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = verifySource();
  if (process.argv[2]) Object.assign(result, verifyDocx(fs.readFileSync(process.argv[2])));
  console.log(JSON.stringify(result, null, 2));
  if (Object.values(result).some((v) => !v)) process.exitCode = 1;
}

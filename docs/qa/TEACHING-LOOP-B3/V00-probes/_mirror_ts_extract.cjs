/**
 * V00 契约镜像对比辅助：用 TypeScript 编译器解析 TS 契约，输出结构化 JSON。
 * 用法：node _mirror_ts_extract.cjs <file.ts> [more.ts ...]
 * 输出：{ "<file>": { "<TypeName>": {kind, members:[{name,optional,type}], extends:[...]} } }
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const out = {};
for (const file of process.argv.slice(2)) {
  const text = fs.readFileSync(file, 'utf8');
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const entries = {};
  for (const statement of source.statements) {
    if (ts.isInterfaceDeclaration(statement)) {
      entries[statement.name.text] = {
        kind: 'interface',
        extends: (statement.heritageClauses || []).flatMap((clause) =>
          clause.types.map((type) => type.getText(source)),
        ),
        members: statement.members
          .filter((member) => ts.isPropertySignature(member))
          .map((member) => ({
            name: member.name.getText(source),
            optional: Boolean(member.questionToken),
            type: member.type ? member.type.getText(source) : 'any',
          })),
      };
    } else if (ts.isTypeAliasDeclaration(statement)) {
      entries[statement.name.text] = {
        kind: 'alias',
        type: statement.type.getText(source),
      };
    }
  }
  out[file] = entries;
}
process.stdout.write(JSON.stringify(out));

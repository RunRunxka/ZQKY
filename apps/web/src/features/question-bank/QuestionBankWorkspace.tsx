'use client';

/**
 * `/question-bank` 题库页（R4-FE 2026-10-11）。
 *
 * 参考图形态：顶部筛选条 + 左「知识点分类」树 + 右「题目列表」；导入与新增收进面板。
 * 页面只渲染业务内容——公共壳与滚动容器由 layout 的 `ModuleWorkspaceShell` 统一提供
 * （`question-bank` 由总控登记为业务根），本页不自包 WorkspaceShell、不写滚动兜底。
 *
 * 数据全部来自 FastAPI（`/api/v1/...`）；分类字典读取失败只影响筛选选项与标签显示，
 * 题目与知识点分类各自三态呈现，失败一律显示原因，不当空目录。
 */

import { useMemo, useRef } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';
// 与既有内容页共享 space 设计语言（只读引入，不修改共享层）
import '@/components/layout/space.css';
import '@/features/question-bank/styles/question-bank.css';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { QuestionLibrary } from './QuestionLibrary';
import { useAsyncResource } from './hooks';
import { buildTaxonomyIndex } from './taxonomy';

export function QuestionBankWorkspace() {
  const pageRef = useRef<HTMLDivElement>(null);
  useEntrance(pageRef, { preset: 'page' });

  const taxonomy = useAsyncResource((signal) => fetchTextbookTaxonomy(signal), 'question-bank-taxonomy');
  const index = useMemo(
    () => buildTaxonomyIndex(taxonomy.state.phase === 'ready' ? taxonomy.state.data : null),
    [taxonomy.state],
  );

  return (
    <div ref={pageRef} className="space-page question-bank-page">
      <header className="space-header" data-motion-reveal>
        <div className="space-header-row">
          <h1>题库</h1>
        </div>
        <p className="space-description">
          按知识点与难度分类的题目库；题目来自教材课后习题提取与文件导入，AI 结果只是待校对建议，
          人工校对确认后才入库。
        </p>
      </header>

      <main className="space-content">
        {taxonomy.state.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            分类字典读取失败（{taxonomy.state.error.code}）：{taxonomy.state.error.message}
            学科/年级/版本标签与导入分类选项暂不可用；题目与知识点数据不受影响。
            <div className="qb-actions">
              <button className="space-button" onClick={taxonomy.reload}>
                重试读取字典
              </button>
            </div>
          </div>
        )}

        <QuestionLibrary taxonomy={index} />

        <p className="space-footnote">
          列表、分类计数与批次状态都以后端为准：任何环节失败都会显示具体原因与错误码，不会伪造成功，
          也不会把请求失败当成空列表。
        </p>
      </main>
    </div>
  );
}

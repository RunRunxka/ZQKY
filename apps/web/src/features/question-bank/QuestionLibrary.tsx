'use client';

/**
 * 题库主体（参考图布局，R4-FE 2026-10-11）：
 * 顶部筛选条卡片（选择知识点 / 难度 / 搜索题目 + 添加题目 / 批量导入）
 * + 左卡「知识点分类」（树 + 计数）+ 右卡「题目列表」（题干 / 难度徽标 / 编辑 / 删除 + 分页）。
 *
 * 归档版的「导入批次 / 已入库题目」两个页签按参考图收拢：题目列表成为首页主体，
 * 导入相关动作（文件上传、教材课后习题提取、批次列表）收进「批量导入」面板，
 * 手动录入与 AI 补题收进「添加题目」面板。
 *
 * 数据全部来自 FastAPI；筛选条件变化重置到第一页；任何失败都显示错误码与重试，不当空列表。
 */

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { KnowledgePointView } from '@/contracts/knowledge';
import type { QuestionSummary } from '@/contracts/question-bank';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import { AddQuestionPanel } from './AddQuestionPanel';
import { BatchImportPanel } from './BatchImportPanel';
import { useAsyncResource, type AsyncState } from './hooks';
import { KnowledgeTreePanel } from './KnowledgeTreePanel';
import { QuestionDetailPanel } from './QuestionDetailPanel';
import { QuestionFilterBar } from './QuestionFilterBar';
import { EMPTY_QUESTION_FILTERS, QuestionListCard, type QuestionFilters } from './QuestionListCard';
import type { TaxonomyIndex } from './taxonomy';

const POINT_PAGE_LIMIT = 200;

export function QuestionLibrary({ taxonomy }: { taxonomy: TaxonomyIndex }) {
  const router = useRouter();
  const [filters, setFilters] = useState<QuestionFilters>(EMPTY_QUESTION_FILTERS);
  const [offset, setOffset] = useState(0);
  const [refreshToken, setRefreshToken] = useState(0);
  const [openQuestion, setOpenQuestion] = useState<{ id: string; editing: boolean } | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  const points = useAsyncResource(
    (signal) => listKnowledgePoints({ limit: POINT_PAGE_LIMIT }, signal),
    'qb-points',
  );
  const pointsState: AsyncState<KnowledgePointView[]> = useMemo(
    () =>
      points.state.phase === 'ready'
        ? { phase: 'ready', data: points.state.data.items }
        : points.state,
    [points.state],
  );

  function applyFilters(next: QuestionFilters) {
    setFilters(next);
    setOffset(0);
  }

  function openEditor(question: QuestionSummary) {
    setOpenQuestion({ id: question.questionId, editing: true });
  }

  return (
    <section className="qb-library" aria-label="题库">
      <QuestionFilterBar
        points={pointsState}
        onReloadPoints={points.reload}
        filters={filters}
        onFiltersChange={applyFilters}
        onOpenAdd={() => setAddOpen(true)}
        onOpenImport={() => setImportOpen(true)}
      />

      <div className="space-bank-layout">
        <KnowledgeTreePanel
          points={pointsState}
          onReloadPoints={points.reload}
          filters={filters}
          selectedId={filters.knowledgePointId}
          onSelect={(knowledgePointId) => applyFilters({ ...filters, knowledgePointId })}
          refreshToken={refreshToken}
        />
        <QuestionListCard
          filters={filters}
          offset={offset}
          onOffsetChange={setOffset}
          refreshToken={refreshToken}
          onEdit={openEditor}
          onDeleted={() => setRefreshToken((value) => value + 1)}
          onAdd={() => setAddOpen(true)}
        />
      </div>

      {importOpen && (
        <BatchImportPanel taxonomy={taxonomy} onClose={() => setImportOpen(false)} />
      )}

      {addOpen && (
        <AddQuestionPanel
          taxonomy={taxonomy}
          onClose={() => setAddOpen(false)}
          onPublished={() => setRefreshToken((value) => value + 1)}
          onImported={(importId) => {
            setAddOpen(false);
            setRefreshToken((value) => value + 1);
            router.push(`/question-bank/imports/${encodeURIComponent(importId)}`);
          }}
        />
      )}

      {openQuestion && (
        <QuestionDetailPanel
          questionId={openQuestion.id}
          taxonomy={taxonomy}
          initialEditing={openQuestion.editing}
          onClose={() => setOpenQuestion(null)}
          onChanged={() => setRefreshToken((value) => value + 1)}
        />
      )}
    </section>
  );
}

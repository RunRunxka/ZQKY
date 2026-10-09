'use client';

/**
 * 教案「生成前置」五步清单的展示外壳（F2-LOOP 方向 02 闭环传递带 · 教案工位）。
 *
 * 每步行四段：编号+名称 / why（为什么需要）/ where（去哪里准备）/ 状态徽标
 * （`▣ 就绪 · 细节` 或 `▢ 未就绪` + 「去…」）。控件本身仍由 SourcePanel 原样提供，
 * 这里只加排版、状态与说明：不读取来源、不写入、不伪造就绪。
 * 徽标沿用传递带的 ▣/▢ 语言与既有 token，不新增独立主题或动画。
 */
import type { ReactNode, Ref } from 'react';

export interface ChecklistStepView {
  /** 稳定键：data-step 与 aria-labelledby 共用。 */
  id: string;
  /** 圈号，如 ①。 */
  no: string;
  title: string;
  why: string;
  where: string;
  ready: boolean;
  /** 完整状态文案（含 ▣/▢ 前缀与「· 细节」）。 */
  stateText: string;
  /** 未就绪时的「去…」按钮/链接；就绪时不渲染。 */
  action?: ReactNode;
}

export function ChecklistSummary({ readyCount, total, missing }: { readyCount: number; total: number; missing: string[] }) {
  return (
    <div className="lesson-wizard-summary" data-ready={readyCount} data-total={total}>
      <span className="lesson-wizard-score">就绪 {readyCount}/{total}</span>
      {missing.length > 0
        ? <span className="lesson-wizard-missing">未就绪：{missing.join('、')}</span>
        : <span className="lesson-wizard-missing">五步齐备</span>}
    </div>
  );
}

export function ChecklistStep({ step, rootRef, children }: { step: ChecklistStepView; rootRef?: Ref<HTMLElement>; children?: ReactNode }) {
  const labelId = `lesson-wizard-${step.id}`;
  return (
    <section className="lesson-wizard-step" data-state={step.ready ? 'ready' : 'todo'} data-step={step.id} ref={rootRef} aria-labelledby={labelId}>
      <div className="lesson-wizard-head">
        <span className="lesson-wizard-no" id={labelId}>{step.no} {step.title}</span>
        <span className="lesson-wizard-state">
          <span className="lesson-wizard-state-text">{step.stateText}</span>
          {step.action}
        </span>
      </div>
      <p className="lesson-wizard-why">{step.why}</p>
      <p className="lesson-wizard-where">{step.where}</p>
      {children ? <div className="lesson-wizard-body">{children}</div> : null}
    </section>
  );
}

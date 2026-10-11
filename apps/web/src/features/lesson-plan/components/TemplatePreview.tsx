'use client';
import { useMemo } from 'react';
import { Printer } from 'lucide-react';
import type { LessonPlanData, ProcessItemV2, ProcessPhase } from '@/contracts/lesson-plans';
import { fontFamilyOf, processToV2, type LessonStyleState } from '../model/modules';

const PHASE_LABELS: Record<ProcessPhase, string> = {
  warmup: '课前热身', introduction: '课程引入', exploration: '深入研讨', practice: '练习巩固', conclusion: '总结提升',
};

/**
 * 三栏式右栏（C3-2）：A4 纸实时预览，**从模板第 3 页的正文起**（封面/目录不预览，
 * 导出时自动补上）；模块显隐与字体/字号/行高即时生效。
 */
export function TemplatePreview({
  data,
  style,
  onPrint,
}: {
  data: LessonPlanData;
  style: LessonStyleState;
  onPrint?(): void;
}) {
  const basic = data.basic ?? { courseName: '', teacher: '', audience: '', hours: '', teachingTime: '', location: '', chapter: '' };
  const analysis = data.analysis ?? { learning: '', textbook: '', content: '', ideological: '' };
  const strategy = data.strategy ?? { designThinking: '', teachingFlow: '', methods: '' };
  const evaluation = data.evaluation ?? { afterClassTest: '', homework: '' };
  const rows = useMemo(() => processToV2(data), [data]);
  const hidden = style.hiddenModules;

  // 阶段分组（保持出现顺序）
  const phaseGroups = useMemo(() => {
    const groups: { phase: ProcessPhase; label: string; rows: ProcessItemV2[] }[] = [];
    for (const row of rows) {
      const last = groups.at(-1);
      if (last && last.phase === row.phase) last.rows.push(row);
      else groups.push({ phase: row.phase, label: row.phaseLabel || PHASE_LABELS[row.phase], rows: [row] });
    }
    return groups;
  }, [rows]);

  const paperStyle = {
    fontFamily: fontFamilyOf(style.fontId),
    fontSize: `${style.fontSize}px`,
    lineHeight: style.lineHeight,
  } as const;

  return (
    <div className="lesson-tpl-preview">
      <div className="lesson-tpl-toolbar">
        <button className="icon-button" aria-label="打印教案" onClick={onPrint}>
          <Printer size={15} aria-hidden />
        </button>
      </div>
      <div className="lesson-tpl-paper" style={paperStyle} data-testid="lesson-template-preview">
        <h1 className="lesson-tpl-heading">{data.title || '（课题名称）'}　教学设计</h1>
        {!hidden.includes('basic') && (
          <section className="lesson-tpl-section">
            <table className="lesson-tpl-table">
              <tbody>
                <tr><th>课程名称</th><td>{basic.courseName || data.title}</td><th>授课对象</th><td>{basic.audience}</td></tr>
                <tr><th>授课时间</th><td>{basic.teachingTime}</td><th>授课地点</th><td>{basic.location}</td></tr>
                <tr><th>授课教师</th><td>{basic.teacher}</td><th>授课学时</th><td>{basic.hours}</td></tr>
                <tr><th>教学章节</th><td colSpan={3}>{basic.chapter}</td></tr>
              </tbody>
            </table>
          </section>
        )}
        {!hidden.includes('analysis') && (
          <section className="lesson-tpl-section">
            <table className="lesson-tpl-table">
              <tbody>
                <TemplateRow title="二、教学分析" />
                <Row label="学情分析" text={analysis.learning} />
                <Row label="教材分析" text={analysis.textbook} />
                <Row label="教学内容" text={analysis.content} />
                <Row label="思政资源" text={analysis.ideological} />
              </tbody>
            </table>
          </section>
        )}
        {!hidden.includes('objectives') && (
          <section className="lesson-tpl-section">
            <table className="lesson-tpl-table">
              <tbody>
                <TemplateRow title="三、教学目标" />
                <Row label="教学目标" text={data.coreCompetencies} />
                <Row label="教学重点" text={data.keyPoints} />
              </tbody>
            </table>
          </section>
        )}
        {!hidden.includes('strategy') && (
          <section className="lesson-tpl-section">
            <table className="lesson-tpl-table">
              <tbody>
                <TemplateRow title="四、教学策略" />
                <Row label="设计思路" text={strategy.designThinking} />
                <Row label="教学流程" text={strategy.teachingFlow} />
                <Row label="教学手段" text={strategy.methods} />
              </tbody>
            </table>
          </section>
        )}
        {!hidden.includes('process') && (
          <section className="lesson-tpl-section">
            <table className="lesson-tpl-table lesson-tpl-process">
              <tbody>
                <TemplateRow title="五、教学过程" />
                <tr className="lesson-tpl-thead">
                  <th colSpan={4}>教学环节 ｜ 教师活动 ｜ 学生活动 ｜ 设计意图</th>
                </tr>
                {phaseGroups.map((group) => (
                  <FragmentRow key={`${group.phase}-${group.label}`} label={group.label} rows={group.rows} />
                ))}
                {rows.length === 0 && (
                  <tr><th>—</th><td colSpan={3}>（暂无环节）</td></tr>
                )}
              </tbody>
            </table>
          </section>
        )}
        {!hidden.includes('exercises') && (
          <section className="lesson-tpl-section">
            <table className="lesson-tpl-table">
              <tbody>
                <TemplateRow title="六、评价反馈" />
                <Row label="练习与作业" text={data.exercises} />
                <Row label="课后测试情况" text={evaluation.afterClassTest} />
                <Row label="作业情况" text={evaluation.homework} />
              </tbody>
            </table>
          </section>
        )}
        {!hidden.includes('reflection') && (
          <section className="lesson-tpl-section">
            <table className="lesson-tpl-table">
              <tbody>
                <TemplateRow title="七、教学反思" />
                <Row label="教学反思" text={data.reflection} />
              </tbody>
            </table>
          </section>
        )}
      </div>
    </div>
  );
}

function TemplateRow({ title }: { title: string }) {
  return (
    <tr className="lesson-tpl-band"><th colSpan={4}>{title}</th></tr>
  );
}

function Row({ label, text }: { label: string; text: string }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td colSpan={3}>{text ? <MultiText text={text} /> : <span className="lesson-tpl-empty">待填写</span>}</td>
    </tr>
  );
}

function FragmentRow({ label, rows }: { label: string; rows: ProcessItemV2[] }) {
  return (
    <>
      <tr className="lesson-tpl-phase"><th colSpan={4}>{label}</th></tr>
      {rows.map((row) => (
        <tr key={row.id}>
          <th scope="row">{row.title || '（环节）'}</th>
          <td>{row.teacherActivity ? <MultiText text={row.teacherActivity} /> : <span className="lesson-tpl-empty">待填写</span>}</td>
          <td>{row.studentActivity ? <MultiText text={row.studentActivity} /> : <span className="lesson-tpl-empty">待填写</span>}</td>
          <td>{row.intent ? <MultiText text={row.intent} /> : <span className="lesson-tpl-empty">待填写</span>}</td>
        </tr>
      ))}
    </>
  );
}

/** 多行文本（\n 分段），预览与编辑一致。 */
function MultiText({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n+/).map((line, i) => (
        <span key={i} className="lesson-tpl-line">{line}</span>
      ))}
    </>
  );
}

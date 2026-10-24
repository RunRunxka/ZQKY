'use client';
/**
 * 工作台帮助（magic-resume FAQ orb 的教案版）：模板结构、快捷键、保存与导出说明。
 *
 * 只解释真实行为：封面/目录导出时生成、AI 先候选、隐藏模块只影响预览、图片类内容按文本排入。
 */
import { BookOpen, Keyboard, Save, ShieldCheck } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';

const SECTIONS: Array<{ no: string; title: string; hint: string }> = [
  { no: '一', title: '基本信息', hint: '课程名称 / 授课对象 / 授课时间 / 授课地点 / 教学章节' },
  { no: '二', title: '教学分析', hint: '学情分析 / 教材分析 / 教学内容 / 思政资源' },
  { no: '三', title: '教学目标', hint: '知识 / 能力 / 思政 三行 + 教学重点、教学难点' },
  { no: '四', title: '教学策略', hint: '设计思路 / 教学流程 / 教学手段（与目标同表）' },
  { no: '五', title: '教学过程', hint: '两行表头 + 阶段行 + 环节行（教师 / 学生活动 / 设计意图）' },
  { no: '六', title: '评价反馈', hint: '课后测试 / 课后作业 / 课后调查 / 督导反馈' },
  { no: '七', title: '教学反思', hint: '目标达成度 / 教学特色 / 教学后记' },
];

const SHORTCUTS: Array<[string, string]> = [
  ['Ctrl / ⌘ + Z', '撤销'],
  ['Ctrl / ⌘ + Shift + Z', '重做（也支持 Ctrl / ⌘ + Y）'],
  ['Ctrl / ⌘ + S', '立即保存（本地草稿 + 云端同步）'],
  ['Ctrl / ⌘ + P', '打印当前预览'],
  ['Esc', '关闭弹层'],
];

export function WorkbenchHelp({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="教案工作台帮助" onClose={onClose}>
      <div className="lw-help" data-testid="lw-help">
        <section className="lw-help-section">
          <h3>
            <BookOpen size={15} aria-hidden />
            模板结构
          </h3>
          <p className="lw-help-lead">
            导出使用仓库内的《教学设计》空白模板：第 1 页封面、第 2 页目录、第 3 页起正文四张表。
            预览只排正文，封面与目录在导出时自动补齐；目录页码与预览分页同源。
          </p>
          <ol className="lw-help-list">
            {SECTIONS.map((entry) => (
              <li key={entry.no}>
                <span className="lw-help-no">{entry.no}</span>
                <span className="lw-help-name">{entry.title}</span>
                <span className="lw-help-hint">{entry.hint}</span>
              </li>
            ))}
          </ol>
          <p className="lw-help-note">
            模板目录末尾还有「附件一 课前测试 / 附件二 调查问卷 / 附件三 课后测试与主题讨论、作业」，
            导出时保留。
          </p>
        </section>

        <section className="lw-help-section">
          <h3>
            <Keyboard size={15} aria-hidden />
            快捷键
          </h3>
          <dl className="lw-help-keys">
            {SHORTCUTS.map(([keys, action]) => (
              <div key={keys}>
                <dt>
                  <kbd>{keys}</kbd>
                </dt>
                <dd>{action}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="lw-help-section">
          <h3>
            <Save size={15} aria-hidden />
            保存与导出
          </h3>
          <ul className="lw-help-bullets">
            <li>草稿先写本机浏览器（约 0.6 秒防抖），再尽力同步到本机后端（约 0.9 秒防抖，版本冲突会停下询问）。</li>
            <li>导出需要先在「本地教案」里选择学科与班级；教案必须属于某班某科。</li>
            <li>导出会带上当前模块顺序、显隐与排版；自定义模块追加为独立表格。</li>
          </ul>
        </section>

        <section className="lw-help-section">
          <h3>
            <ShieldCheck size={15} aria-hidden />
            预览说明
          </h3>
          <ul className="lw-help-bullets">
            <li>AI 生成内容先进入候选，预览中以「AI 候选」标注；采用后才写入草稿。</li>
            <li>隐藏模块不会出现在预览里；导出仍保留模板固定的七节结构。</li>
            <li>样张中的插图属于图片内容，当前按文本排入；学生个人信息不进模型。</li>
          </ul>
        </section>
      </div>
    </Modal>
  );
}
